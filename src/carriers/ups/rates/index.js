import { RATES } from './publish_data.js'
import { A26_RATES, B26_RATES } from './commercial_data.js'

// =============================================================================
// PERBAIKAN KRITIS #1: UPS A26/B26 Named-Group Override
// Negara-negara tertentu punya tabel rate KHUSUS di A26/B26, bukan zone biasa.
// Tanpa ini, Jepang/Korea/HK/dll menggunakan zone generik → selisih ~6-7%
// =============================================================================

// =============================================================================
// PERBAIKAN KRITIS #1: UPS A26/B26 Named-Group Override (v2 -- direction-aware)
// Negara-negara tertentu punya tabel rate KHUSUS di A26/B26, bukan zone biasa.
// Tanpa ini, Jepang/Korea/HK/dll menggunakan zone generik → selisih ~6-7%
//
// PERBAIKAN v2 (audit lanjutan): versi sebelumnya pakai SATU map flat yang
// TIDAK peduli arah (import/export) -- padahal beberapa grup CUMA ada di
// salah satu arah (mis. "japan, korea, taiwan" itu grup EXPORT; utk IMPORT,
// Jepang justru punya tabel "japan" SENDIRIAN, beda nilai). Dibuktikan
// dengan angka nyata (lihat AUDIT_UPS_COMMERCIAL.md / verifikasi Python):
//   Import saver Korea 2kg : v1 (salah) Rp 633.100 vs benar Rp 580.300
//   Import saver UK 2kg    : v1 (salah) Rp 662.900 vs benar Rp 641.400
//   Import saver Jepang 2kg: v1 (salah) Rp 594.700 vs benar Rp 535.300
// UK grup import ("france germany italy united kingdom") malah TIDAK ADA
// di map v1 sama sekali. Port ulang ini persis meniru struktur Python
// A26_B26_GROUPS (get_extended_group_key di commercial.py).
// =============================================================================

const NAMED_GROUPS = {
    // Export Groups
    'hong kong, philippines, thailand, vietnam':
        ['hong kong', 'philippines', 'thailand', 'vietnam', 'hk', 'ph', 'th', 'vn'],
    'japan, korea, taiwan':
        ['japan', 'korea', 'south korea', 'kr', 'republic of korea', "korea, republic of", 'taiwan', 'jp', 'tw'],
    'france, germany, italy, netherlands':
        ['france', 'germany', 'italy', 'netherlands', 'fr', 'de', 'it', 'nl'],

    // Import Groups
    'south korea taiwan vietnam':
        ['south korea', 'korea', 'kr', 'republic of korea', "korea, republic of", 'taiwan', 'tw', 'vietnam', 'vn'],
    'france germany italy united kingdom':
        ['france', 'germany', 'italy', 'united kingdom', 'uk', 'gb', 'great britain', 'fr', 'de', 'it'],
    'japan': ['japan', 'jp'],

    // Common (sama utk export & import)
    'united states': ['united states', 'usa', 'us'],
    'australia': ['australia', 'au'],
    'rest of china': ['china', 'cn'],
    'china south': ['china south', 'cn southern', 'southern china', 'china southern'],
}

function getGroupKey(countryName, tableSrv) {
    if (!countryName || !tableSrv) return null
    const normalized = countryName.trim().toLowerCase()
    const availableGroups = new Set(Object.keys(tableSrv))

    // EXPLICIT: prioritaskan named header China di atas zone 3 & 10 (sama
    // seperti urutan di Python/script.js -- urutan ini penting).
    if ((normalized === 'china' || normalized === 'rest of china') && availableGroups.has('rest of china')) {
        return 'rest of china'
    }
    if (['cn southern', 'southern china', 'china southern', 'china south'].includes(normalized)
        && availableGroups.has('china south')) {
        return 'china south'
    }

    if (availableGroups.has(normalized)) return normalized

    for (const [groupKey, members] of Object.entries(NAMED_GROUPS)) {
        if (members.includes(normalized) && availableGroups.has(groupKey)) {
            return groupKey
        }
    }
    return null
}

// =============================================================================
// Price lookup helpers
// =============================================================================

function priceFromFlatTable(table, weight) {
    // <= 20kg: flat per-shipment, rounded ke 0.5kg terdekat
    const rounded = Math.round(weight * 2) / 2
    const key = rounded.toFixed(1)
    if (table[key] !== undefined) return table[key]

    const floatKeys = Object.keys(table)
        .filter(k => !isNaN(parseFloat(k)))
        .map(parseFloat)
        .sort((a, b) => a - b)

    for (const k of floatKeys) {
        if (k >= weight - 1e-9) {
            return table[k.toFixed(1)] ?? table[k.toString()]
        }
    }
    return null
}

function priceFromPerKgTable(table, weight) {
    // > 20kg: rate per-kg, bulatkan ke atas (ceil)
    const wCeil = Math.ceil(weight)
    const intKeys = Object.keys(table)
        .filter(k => !isNaN(parseInt(k)) && !k.includes('.'))
        .map(Number)
        .sort((a, b) => a - b)

    for (const k of intKeys) {
        if (wCeil <= k) return table[k.toString()]
    }
    // Ambil key terbesar (>1000 dst)
    if (intKeys.length > 0) return table[intKeys[intKeys.length - 1].toString()]
    return null
}

function priceFromTable(table, weight) {
    if (weight <= 20.0) {
        const rate = priceFromFlatTable(table, weight)
        return rate // flat = harga per shipment, bukan per kg
    }
    const ratePerKg = priceFromPerKgTable(table, weight)
    if (ratePerKg == null) return null
    return ratePerKg * Math.ceil(weight)
}

// =============================================================================
// Publish
// =============================================================================

export function calculateBasePublish(service, direction, zone, weight) {
    const tableDir = direction === 'import' ? RATES.import : RATES.export
    if (!tableDir) return null

    const tableSrv = tableDir[service]
    if (!tableSrv) return null

    const tableZone = tableSrv[zone.toString()]
    if (!tableZone) return null

    return priceFromTable(tableZone, weight)
}

// =============================================================================
// Commercial A26 / B26 dengan Named-Group Override
// =============================================================================

export function calculateBaseCommercial(rateType, service, direction, zone, weight, country) {
    const db = rateType === 'a26' ? A26_RATES : B26_RATES

    const tableDir = direction === 'import' ? db.import : db.export
    if (!tableDir) return null

    const tableSrv = tableDir[service]
    if (!tableSrv) return null

    // Coba named-group dulu
    let tableZone = null
    const groupKey = getGroupKey(country, tableSrv)
    if (groupKey && tableSrv[groupKey]) {
        tableZone = tableSrv[groupKey]
    }

    // Fallback ke zone numerik/string
    if (!tableZone) {
        tableZone = tableSrv[zone.toString()]
    }
    if (!tableZone) {
        const lowerZone = zone.toString().toLowerCase()
        for (const [k, v] of Object.entries(tableSrv)) {
            if (k.toLowerCase() === lowerZone) {
                tableZone = v
                break
            }
        }
    }

    if (!tableZone) return null
    return priceFromTable(tableZone, weight)
}

// =============================================================================
// Entry point
// =============================================================================

export function calculateBase(rateType, service, direction, zone, weight, country = '') {
    const rt = rateType.toLowerCase()
    if (rt === 'publish') {
        return calculateBasePublish(service, direction, zone, weight)
    } else if (rt === 'a26' || rt === 'b26') {
        return calculateBaseCommercial(rt, service, direction, zone, weight, country)
    }
    throw new Error(`rate_type '${rateType}' tidak dikenal untuk UPS.`)
}
