/**
 * FedEx ODA/OPA Lookup (JavaScript port dari Python oda_opa.py)
 * ==============================================================
 * OPA = Out-of-Pickup-Area   → sisi PICKUP (ekspor dari Indo, atau origin luar)
 * ODA = Out-of-Delivery-Area → sisi DELIVERY (impor ke Indo, atau dest luar)
 *
 * Data: oda_opa_data.json (~5MB, 62.641 postal ranges + 4.961 kota, 112 negara)
 * Tier: No | A | B | C
 * Effective: 13 Jul 2026
 */

import data from './oda_opa_data.json' with { type: 'json' }

const { range_index, city_index, country_names, name_to_code } = data

// ─── Tarif OPA (Out-of-Pickup-Area) ────────────────────────────
// Tier A tidak berlaku untuk OPA
export const OPA_TARIFF = {
    'No': { per_shipment: 0,      per_kg: 0    },
    'A':  { per_shipment: 0,      per_kg: 0    },
    'B':  { per_shipment: 339000, per_kg: 6000 },
    'C':  { per_shipment: 442000, per_kg: 8000 },
}

// ─── Tarif ODA (Out-of-Delivery-Area) ──────────────────────────
export const ODA_TARIFF = {
    'No': { per_shipment: 0,      per_kg: 0    },
    'A':  { per_shipment: 52000,  per_kg: 0    },   // flat only
    'B':  { per_shipment: 339000, per_kg: 6000 },
    'C':  { per_shipment: 442000, per_kg: 8000 },
}

const SEVERITY = { 'No': 0, 'A': 1, 'B': 2, 'C': 3 }

function mergeTiers(tiersList) {
    const merged = { pp: 'No', fp: 'No', pd: 'No', fd: 'No' }
    for (const t of tiersList) {
        for (const k of Object.keys(merged)) {
            const v = (t[k] || 'No').trim() || 'No'
            if ((SEVERITY[v] ?? 0) > (SEVERITY[merged[k]] ?? 0)) {
                merged[k] = v
            }
        }
    }
    return merged
}

function isNumeric(s) {
    return /^\d+$/.test(s)
}

function normalizePostal(p) {
    return p.trim().toUpperCase().replace(/[\s\-]/g, '')
}

// ─── Resolve country code ───────────────────────────────────────
export function resolveCountryCode(country) {
    const key = country.trim()
    if (key.length === 2 && country_names[key.toUpperCase()]) return key.toUpperCase()
    const lower = key.toLowerCase()
    if (name_to_code[lower]) return name_to_code[lower]
    // partial match
    const matches = new Set(
        Object.entries(name_to_code)
            .filter(([name]) => name.includes(lower) || lower.includes(name))
            .map(([, code]) => code)
    )
    if (matches.size === 1) return [...matches][0]
    return null  // negara tidak ada di ODA/OPA data
}

// ─── Postal range match ─────────────────────────────────────────
function matchPostal(cc, postalCode) {
    const candidates = range_index[cc]
    if (!candidates) return null

    const norm = normalizePostal(postalCode)
    const numericInput = isNumeric(norm)
    const numInput = numericInput ? parseInt(norm, 10) : null

    const matched = []
    for (const c of candidates) {
        if (c.n && numericInput) {
            if (parseInt(c.b, 10) <= numInput && numInput <= parseInt(c.e, 10)) {
                matched.push(c.t)
            }
        } else if (!c.n && !numericInput) {
            const b = normalizePostal(c.b)
            const e = normalizePostal(c.e)
            if (b <= norm && norm <= e) {
                matched.push(c.t)
            }
        }
    }

    if (matched.length === 0) return null
    if (matched.length === 1) return matched[0]
    return mergeTiers(matched)
}

// ─── City match ─────────────────────────────────────────────────
function matchCity(cc, city) {
    const cities = city_index[cc]
    if (!cities) return null
    return cities[city.trim().toLowerCase()] ?? null
}

// ─── Main lookup ────────────────────────────────────────────────
/**
 * Lookup ODA/OPA tiers untuk satu negara+postal/kota.
 * @param {string} country - nama negara atau kode 2-huruf
 * @param {string|null} postalCode
 * @param {string|null} city
 * @returns {{ found: boolean, match_by: string, tiers: object|null, country_code: string|null }}
 */
export function lookup(country, postalCode = null, city = null) {
    const cc = resolveCountryCode(country)
    if (!cc) {
        return { found: false, match_by: 'country_not_listed', tiers: null, country_code: null }
    }

    let tiers = null
    let match_by = 'not_found'

    if (postalCode) {
        tiers = matchPostal(cc, postalCode)
        if (tiers) match_by = 'postal_code'
    }
    if (!tiers && city) {
        tiers = matchCity(cc, city)
        if (tiers) match_by = 'city'
    }

    return {
        found: tiers !== null,
        match_by,
        tiers,
        country_code: cc,
        country_name: country_names[cc] ?? country,
    }
}

// ─── Charge computation ─────────────────────────────────────────
/**
 * Hitung biaya ODA/OPA dalam IDR.
 * @param {'oda'|'opa'} kind
 * @param {'No'|'A'|'B'|'C'} tier
 * @param {number} weight_kg - chargeable weight
 * @returns {number} - IDR charge
 */
export function computeCharge(kind, tier, weight_kg) {
    const tariffTable = kind === 'opa' ? OPA_TARIFF : ODA_TARIFF
    const t = tariffTable[tier] ?? tariffTable['No']
    const perShipment = t.per_shipment
    const perKgTotal  = t.per_kg * weight_kg
    return Math.max(perShipment, perKgTotal)
}

/**
 * Fungsi high-level: cek ODA/OPA untuk satu sisi shipment dan kembalikan charge (IDR).
 * @param {'opa'|'oda'} kind
 * @param {'parcel'|'freight'} serviceType
 * @param {string} country
 * @param {string|null} postalCode
 * @param {string|null} city
 * @param {number} weight_kg
 * @returns {{ charge: number, tier: string, match_by: string }}
 */
export function lookupAndCompute(kind, serviceType, country, postalCode, city, weight_kg) {
    const result = lookup(country, postalCode, city)

    if (!result.found) {
        return { charge: 0, tier: 'No', match_by: result.match_by }
    }

    // Ambil tier yang sesuai (pp/fp/pd/fd)
    // pp=parcel_pickup, fp=freight_pickup, pd=parcel_delivery, fd=freight_delivery
    const tierKey = serviceType === 'freight'
        ? (kind === 'opa' ? 'fp' : 'fd')
        : (kind === 'opa' ? 'pp' : 'pd')

    const tier   = result.tiers[tierKey] ?? 'No'
    const charge = computeCharge(kind, tier, weight_kg)

    return { charge, tier, match_by: result.match_by }
}
