import { getZone, getZoneCommercial } from './zones.js'
import { calculateBase } from './rates/index.js'
import { computeDemandSurcharge, computeOdaOpaCharge } from './surcharges/core.js'
import { calculateDimWeight, MINIMUM_BILLED_WEIGHT_KG } from './rules.js'

export function calculate(request) {
    const direction = request.direction.toLowerCase()
    const service = request.service.toUpperCase()
    const isImport = direction === 'import'

    let country = isImport ? request.origin_country : request.destination_country
    let postalCode = isImport ? request.postal_code_origin : request.postal_code_destination

    let zone;
    if (request.rate_type === 'commercial') {
        zone = getZoneCommercial(country, isImport, postalCode, null)
    } else {
        zone = getZone(country, isImport, postalCode, null)
    }

    let dimWeight = 0;
    if (request.dimensions_cm && request.dimensions_cm.length === 3) {
        dimWeight = calculateDimWeight(request.dimensions_cm[0], request.dimensions_cm[1], request.dimensions_cm[2])
    }
    
    let chargeableWeight = Math.max(request.weight_kg, dimWeight, MINIMUM_BILLED_WEIGHT_KG)
    
    let basePrice = calculateBase(request.rate_type, service, direction, zone[service], chargeableWeight)
    if (basePrice === null) {
        throw new Error(`Kombinasi direction='${direction}' service='${service.toLowerCase()}' tidak valid (atau weight out of bounds).`)
    }

    let discount = 0
    if (request.discount_pct) {
        discount = basePrice * (request.discount_pct / 100)
    }
    const discountedBase = basePrice - discount

    const surcharges = {}
    
    // Demand Surcharge
    const demand = computeDemandSurcharge(service, isImport, chargeableWeight)
    if (demand > 0) surcharges['Demand Surcharge'] = demand

    // Fuel Surcharge
    let fsiAmount = 0
    if (request.extra && request.extra.fsi_pct) {
        let fsiBase = discountedBase
        for (const v of Object.values(surcharges)) fsiBase += v
        fsiAmount = fsiBase * (request.extra.fsi_pct / 100)
        surcharges[`Fuel Surcharge (${request.extra.fsi_pct}%)`] = Math.round(fsiAmount)
    }
    
    // Total
    let totalSurcharges = 0
    for (const v of Object.values(surcharges)) totalSurcharges += v
    
    const total = discountedBase + totalSurcharges

    return {
        carrier: 'fedex',
        rate_type: request.rate_type,
        service: service,
        zone: zone,
        base_price: Math.round(basePrice),
        surcharges: surcharges,
        discount: Math.round(discount),
        total: Math.round(total),
        currency: 'IDR',
        notes: [],
        extra: {
            chargeable_weight: chargeableWeight,
            dim_weight: dimWeight
        }
    }
}

export default { calculate }
