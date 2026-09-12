import { RATES } from './publish_data.js'
import { COMMERCIAL_RATES } from './commercial_data.js'
import { pyRound } from '../../../core/pyround.js'

// =============================================================================
// FedEx rate table structure (dari Python):
// table = { doc, pak, envelope, band, min_kg, has_legs }
//   - doc    : { "0.5": {A:..., B:...}, "1.0": {...}, ... }  (flat, ≤20.5kg)
//   - band   : [ [min_kg, label, {A:...,B:...}], ... ] (per-kg)
//             ATAU { "door_to_door": [...], "door_to_airport": [...], ... }  (IPF has_legs)
// =============================================================================

function resolveBand(table, legType = 'door_to_door') {
    const raw = table.band
    if (!raw) return null
    if (Array.isArray(raw)) return raw          // IP / IE
    if (raw[legType]) return raw[legType]        // IPF / IEF (has_legs)
    // fallback ke kunci pertama
    const first = Object.values(raw)[0]
    return Array.isArray(first) ? first : null
}

function priceFromTable(table, zone, service, weight_kg, legType = 'door_to_door') {
    let billed = weight_kg
    const min_kg = table.min_kg || 0
    if (min_kg && billed < min_kg) billed = min_kg

    const srv = service.toUpperCase()

    // 0) FedEx Envelope: IP ≤0.5kg
    if (srv === 'IP' && table.envelope && billed <= 0.5) {
        return table.envelope[0.5]?.[zone] ?? null
    }

    // 1) FedEx Pak: IP 0.5–2.5kg
    if (srv === 'IP' && table.pak && billed > 0.5 && billed <= 2.5) {
        const steps = Object.keys(table.pak).map(Number).sort((a, b) => a - b)
        for (const s of steps) {
            if (billed <= s + 1e-9) {
                const pakStep = table.pak[s] ?? table.pak[s.toFixed(1)] ?? table.pak[s.toString()]
                if (pakStep?.[zone] != null) return pakStep[zone]
            }
        }
    }

    // 2) Doc table (flat per-shipment, ≤20.5kg)
    if (table.doc && billed <= 20.5) {
        const steps = Object.keys(table.doc).map(Number).sort((a, b) => a - b)
        for (const s of steps) {
            if (billed <= s + 1e-9) {
                const docStep = table.doc[s] ?? table.doc[s.toFixed(1)] ?? table.doc[s.toString()]
                if (docStep?.[zone] != null) return docStep[zone]
            }
        }
    }

    // 3) Per-kg band
    const bands = resolveBand(table, legType)
    if (!bands) return null

    let chosen = null
    for (const entry of bands) {
        const [min_band, label, rates] = entry
        if (billed >= min_band) chosen = rates
    }
    if (!chosen) return null

    const perKg = chosen[zone]
    if (perKg == null) return null
    return pyRound(perKg * Math.ceil(billed))
}

// =============================================================================
// Publish
// =============================================================================

export function calculateBasePublish(service, direction, zone, weight) {
    const isImport = direction.toLowerCase() === 'import'
    const srv = service.toUpperCase()
    const tableDir = isImport ? RATES.import : RATES.export
    if (!tableDir) return null
    const tableSrv = tableDir[srv]
    if (!tableSrv) return null
    return priceFromTable(tableSrv, zone, srv, weight)
}

// =============================================================================
// Commercial
// =============================================================================

export function calculateBaseCommercial(service, direction, zone, weight) {
    const isImport = direction.toLowerCase() === 'import'
    const srv = service.toUpperCase()
    const tableDir = isImport ? COMMERCIAL_RATES.import : COMMERCIAL_RATES.export
    if (!tableDir) return null
    const tableSrv = tableDir[srv]
    if (!tableSrv) return null
    return priceFromTable(tableSrv, zone, srv, weight)
}

// =============================================================================
// Entry point
// =============================================================================

export function calculateBase(rateType, service, direction, zone, weight) {
    const rt = rateType.toLowerCase()
    if (rt === 'publish' || rt === 'promotional') {
        return calculateBasePublish(service, direction, zone, weight)
    } else if (rt === 'commercial') {
        return calculateBaseCommercial(service, direction, zone, weight)
    }
    throw new Error(`rate_type '${rateType}' tidak dikenal untuk FedEx.`)
}
