import { getZone } from './zones.js'
import { calculateBase } from './rates/index.js'
import { DIM_DIVISOR, COSTS_MAY_24_2026, SURGE_V3, determineSurgeRegion, validateGeometry } from './rules.js'

export function calculate(request) {
    const direction = request.direction.toLowerCase()
    let service = request.service.toLowerCase()
    const isImport = direction === 'import'

    let country = isImport ? request.origin_country : request.destination_country
    let postalCode = isImport ? request.postal_code_origin : request.postal_code_destination

    let zone = getZone(country, direction, service, postalCode)
    
    // Auto WWEF conversion if weight >= 71 and standard service
    if (request.weight_kg >= 71 && (service === "saver" || service === "expedited")) {
        try {
            const wwefZone = getZone(country, direction, "wwef", postalCode);
            if (wwefZone !== null) {
                service = "wwef";
                zone = wwefZone;
            }
        } catch (e) {
            // keep standard service
        }
    }

    let length = request.dimensions_cm ? request.dimensions_cm[0] : 0
    let width = request.dimensions_cm ? request.dimensions_cm[1] : 0
    let height = request.dimensions_cm ? request.dimensions_cm[2] : 0
    
    let dimWeight = 0;
    if (length && width && height) {
        dimWeight = (length * width * height) / DIM_DIVISOR;
    }
    
    let chargeableWeight = Math.max(request.weight_kg, dimWeight)
    if (service === "wwef") {
        chargeableWeight = Math.max(chargeableWeight, 71)
    }
    
    let basePrice = calculateBase(request.rate_type, service, direction, zone, chargeableWeight)
    if (basePrice === null) {
        throw new Error(`Kombinasi direction='${direction}' service='${service}' tidak valid untuk UPS (atau weight out of bounds).`)
    }

    const surcharges = {}
    const geom = validateGeometry(length, width, height)
    
    let isAHS = false
    let isLPS = false
    let isOMX = false
    
    if (request.weight_kg > 70 || geom.L > 274 || geom.girth > 400) {
        isOMX = true
        isLPS = true
    } else if (geom.girth > 300) {
        isLPS = true
    } else if ((request.weight_kg > 25 && request.weight_kg < 71) || (geom.L > 122 || geom.W > 76)) {
        isAHS = true
    }
    
    if (isOMX) {
        surcharges['Over Maximum (OMX)'] = COSTS_MAY_24_2026.OMX
        surcharges['Large Package Surcharge (LPS)'] = COSTS_MAY_24_2026.LPS
        chargeableWeight = Math.max(chargeableWeight, 40)
    } else if (isLPS) {
        surcharges['Large Package Surcharge (LPS)'] = COSTS_MAY_24_2026.LPS
        chargeableWeight = Math.max(chargeableWeight, 40)
    } else if (isAHS) {
        surcharges['Additional Handling (AHS)'] = COSTS_MAY_24_2026.AHS
    }
    
    // Brokerage for Import
    if (isImport && service !== "envelope") {
        surcharges['Brokerage'] = COSTS_MAY_24_2026.BROKERAGE
    }
    
    // Surge Fee
    const region = determineSurgeRegion(country)
    const surgeDict = isImport ? SURGE_V3.import : SURGE_V3.export
    const surgeRate = surgeDict[region] || 0
    if (surgeRate > 0) {
        surcharges['Surge Fee'] = surgeRate * Math.ceil(chargeableWeight)
    }

    let totalSurcharges = 0
    for (const v of Object.values(surcharges)) totalSurcharges += v
    
    const preFsiAmount = basePrice + totalSurcharges
    
    // Fuel Surcharge
    let fsiAmount = 0
    if (request.extra && request.extra.fsi_pct) {
        // UPS FSI calculation excludes Brokerage
        let fsiBase = preFsiAmount
        if (surcharges['Brokerage']) fsiBase -= surcharges['Brokerage']
        
        fsiAmount = fsiBase * (request.extra.fsi_pct / 100)
        surcharges[`Fuel Surcharge (${request.extra.fsi_pct}%)`] = Math.round(fsiAmount)
    }
    
    // VAT
    const preVatAmount = preFsiAmount + fsiAmount
    const vatAmount = preVatAmount * 0.011 // 1.1%
    surcharges['VAT (1.1%)'] = Math.round(vatAmount)
    
    let total = preVatAmount + vatAmount
    
    let discount = 0
    if (request.discount_pct) {
        discount = basePrice * (request.discount_pct / 100)
        total -= discount
    }

    return {
        carrier: 'ups',
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
