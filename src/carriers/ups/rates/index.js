import { RATES } from './publish_data.js'
import { A26_RATES, B26_RATES } from './commercial_data.js'

// =============================================================================
// PERBAIKAN KRITIS #1: UPS A26/B26 Named-Group Override
// Negara-negara tertentu punya tabel rate KHUSUS di A26/B26, bukan zone biasa.
// Tanpa ini, Jepang/Korea/HK/dll menggunakan zone generik → selisih ~6-7%
// =============================================================================

const NAMED_GROUP_MAP = {
    // Japan, Korea, Taiwan
    'japan':       'japan, korea, taiwan',
    'south korea': 'japan, korea, taiwan',
    'taiwan':      'japan, korea, taiwan',
    // HK, Philippines, Thailand, Vietnam
    'hong kong':   'hong kong, philippines, thailand, vietnam',
    'philippines': 'hong kong, philippines, thailand, vietnam',
    'thailand':    'hong kong, philippines, thailand, vietnam',
    'vietnam':     'hong kong, philippines, thailand, vietnam',
    // Standalone groups
    'australia':   'australia',
    'united states': 'united states',
    // China regional
    'china':       'china',
    'cn southern': 'china south',
    // Europe cluster
    'france':      'france, germany, italy, netherlands',
    'germany':     'france, germany, italy, netherlands',
    'italy':       'france, germany, italy, netherlands',
    'netherlands': 'france, germany, italy, netherlands',
}

function getGroupKey(countryName) {
    return NAMED_GROUP_MAP[countryName.toLowerCase()] || null
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
    const groupKey = getGroupKey(country)
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
