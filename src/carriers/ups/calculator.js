import { getZone, effectiveCountryForZone } from './zones.js'
import { calculateBase } from './rates/index.js'
import { pyRound } from '../../core/pyround.js'
import {
    DIM_DIVISOR,
    COSTS_MAY_24_2026,
    SURGE_V3,
    determineSurgeRegion,
    validateGeometry,
    IPF_FEE,
    IPF_ELIGIBLE_SERVICES,
    isUnitedStates,
    packagingTriggersAHS
} from './rules.js'

export function calculate(request) {
    const direction = request.direction.toLowerCase()
    let service    = request.service.toLowerCase()
    const isImport = direction === 'import'

    // Country untuk zone lookup
    const country     = isImport ? request.origin_country      : request.destination_country
    const postalCode  = isImport ? request.postal_code_origin  : request.postal_code_destination
    const countryKey  = country.toLowerCase()

    // === STEP 1: Resolve zone ===
    let zone = getZone(country, direction, service, postalCode)

    // Auto-WWEF jika weight >= 71
    if (request.weight_kg >= 71 && (service === 'saver' || service === 'expedited')) {
        try {
            const wwefZone = getZone(country, direction, 'wwef', postalCode)
            if (wwefZone !== null) {
                service = 'wwef'
                zone = wwefZone
            }
        } catch (_) { /* tetap pakai service semula */ }
    }

    // === STEP 2: Chargeable weight ===
    const length = request.dimensions_cm ? request.dimensions_cm[0] : 0
    const width  = request.dimensions_cm ? request.dimensions_cm[1] : 0
    const height = request.dimensions_cm ? request.dimensions_cm[2] : 0

    let dimWeight = 0
    if (length && width && height) {
        dimWeight = (length * width * height) / DIM_DIVISOR
    }

    // WWEF minimum 71kg
    let chargeableWeight = Math.max(request.weight_kg, dimWeight)
    if (service === 'wwef') {
        chargeableWeight = Math.max(chargeableWeight, 71)
    }

    // === STEP 3: Base rate (kirimkan country utk named-group A26/B26 --
    // pakai effectiveCountryForZone() supaya China Southern via kode pos
    // match ke grup "china south", bukan "rest of china") ===
    const groupCountry = effectiveCountryForZone(country, postalCode)
    let basePrice = calculateBase(request.rate_type, service, direction, zone, chargeableWeight, groupCountry)
    if (basePrice === null) {
        throw new Error(
            `Tidak ada rate tersedia: direction='${direction}' service='${service}' ` +
            `zone='${zone}' weight=${chargeableWeight}kg (UPS)`
        )
    }

    // === STEP 4: Surcharges ===
    const surcharges = {}
    const geom = validateGeometry(length, width, height)

    let adjustedChargeableWeight = chargeableWeight

    if (request.weight_kg > 70 || geom.L > 274 || geom.length_plus_girth > 400) {
        // OMX triggers LPS
        surcharges['Over Maximum (OMX)'] = COSTS_MAY_24_2026.OMX
        surcharges['Large Package Surcharge (LPS)'] = COSTS_MAY_24_2026.LPS
        adjustedChargeableWeight = Math.max(adjustedChargeableWeight, 40)
    } else if (geom.length_plus_girth > 300) {
        surcharges['Large Package Surcharge (LPS)'] = COSTS_MAY_24_2026.LPS
        adjustedChargeableWeight = Math.max(adjustedChargeableWeight, 40)
    } else if (
        (request.weight_kg > 25 && request.weight_kg < 71) ||
        geom.L > 122 || geom.W > 76 ||
        packagingTriggersAHS(request.extra || {})
    ) {
        surcharges['Additional Handling (AHS)'] = COSTS_MAY_24_2026.AHS
    }

    // Brokerage (import saja, bukan envelope)
    if (isImport && service !== 'envelope') {
        surcharges['Brokerage'] = COSTS_MAY_24_2026.BROKERAGE
    }

    // International Processing Fee (IPF) -- otomatis, khusus EKSPOR ke US
    // dgn service Worldwide Saver/Expedited (mewakili WW Express/Express
    // Plus/Express Saver/Expedited -- engine ini cuma model saver &
    // expedited). Tidak berlaku utk envelope/WWEF maupun import.
    if (!isImport && isUnitedStates(country) && IPF_ELIGIBLE_SERVICES.includes(service)) {
        surcharges['International Processing Fee (IPF)'] = IPF_FEE
    }

    // Surge Fee (SURGE_V3)
    const region    = determineSurgeRegion(country)
    const surgeDict = isImport ? SURGE_V3.import : SURGE_V3.export
    const surgeRate = surgeDict[region] ?? 0
    if (surgeRate > 0) {
        surcharges['Surge Fee'] = pyRound(surgeRate * Math.ceil(adjustedChargeableWeight))
    }

    // === STEP 5: FSI ===
    let totalSurchargeBeforeFsi = 0
    for (const v of Object.values(surcharges)) totalSurchargeBeforeFsi += v

    const preFsiTotal = basePrice + totalSurchargeBeforeFsi
    let fsiAmount = 0
    const fsiPct = request.extra?.fsi_pct
    if (fsiPct) {
        // UPS: FSI base = semua kecuali Brokerage
        let fsiBasis = preFsiTotal
        if (surcharges['Brokerage']) fsiBasis -= surcharges['Brokerage']
        fsiAmount = pyRound(fsiBasis * (fsiPct / 100))
        surcharges[`Fuel Surcharge (${fsiPct}%)`] = fsiAmount
    }

    // === STEP 6: VAT 1.1% ===
    const preVatTotal = preFsiTotal + fsiAmount
    const vatAmount = pyRound(preVatTotal * 0.011)
    surcharges['VAT (1.1%)'] = vatAmount

    // === STEP 7: Discount (applied to base only) ===
    let discount = 0
    if (request.discount_pct) {
        discount = pyRound(basePrice * (request.discount_pct / 100))
    }

    const total = pyRound(preVatTotal + vatAmount - discount)

    return {
        carrier: 'ups',
        rate_type: request.rate_type,
        service: service,
        zone: zone,
        base_price: pyRound(basePrice),
        surcharges: surcharges,
        discount: discount,
        total: total,
        currency: 'IDR',
        notes: [],
        extra: {
            chargeable_weight: chargeableWeight,
            dim_weight: dimWeight,
            country: country,
            surge_region: region
        }
    }
}

export default { calculate }
