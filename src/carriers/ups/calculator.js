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
import { computeOptionalSurcharges } from './surcharges/optional.js'
import { computeInsuranceSurcharge } from './surcharges/insurance.js'

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

    // === STEP 2: Chargeable weight (support multi-package via request.packages[]) ===
    // Format lama (dimensions_cm tunggal) TETAP didukung 1:1 spt sebelumnya --
    // ini cuma nambah cabang baru utk multi-collie, bukan ganti yang lama.
    const multiPackage = request.packages && request.packages.length > 0
    let dimWeight = 0
    let chargeableWeight
    let packageGeoms = []  // dipakai lagi di STEP 4 utk cek surcharge per-collie

    if (multiPackage) {
        let sumChargeable = 0
        request.packages.forEach((pkg, i) => {
            const pw = (pkg.length_cm * pkg.width_cm * pkg.height_cm) / DIM_DIVISOR
            const pcw = Math.max(pkg.weight_kg, pw)
            sumChargeable += pcw
            packageGeoms.push({
                geom: validateGeometry(pkg.length_cm, pkg.width_cm, pkg.height_cm),
                weight_kg: pkg.weight_kg,
                label: pkg.label || `Collie ${i + 1}`,
                extra: pkg,  // flag kemasan (non_cardboard_packaging, dll) per-collie
            })
        })
        chargeableWeight = sumChargeable
        // dimWeight (single value) tidak representatif utk multi-collie --
        // dibiarkan 0, dim weight per-collie tetap dipakai dgn benar di atas.
    } else {
        const length = request.dimensions_cm ? request.dimensions_cm[0] : 0
        const width  = request.dimensions_cm ? request.dimensions_cm[1] : 0
        const height = request.dimensions_cm ? request.dimensions_cm[2] : 0

        if (length && width && height) {
            dimWeight = (length * width * height) / DIM_DIVISOR
        }
        chargeableWeight = Math.max(request.weight_kg, dimWeight)
        packageGeoms.push({
            geom: validateGeometry(length, width, height),
            weight_kg: request.weight_kg,
            label: null,
            extra: request.extra || {},
        })
    }

    // WWEF minimum 71kg
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

    // === STEP 4: Surcharges (AHS/LPS/OMX dicek PER-COLLIE kalau multi-package --
    // tiap collie oversize dikenakan surcharge sendiri, sesuai billing UPS
    // per-piece; label dikasih akhiran nama collie kalau lebih dari 1) ===
    const surcharges = {}
    let adjustedChargeableWeight = chargeableWeight

    packageGeoms.forEach(({ geom, weight_kg, label, extra }) => {
        const suffix = label ? ` (${label})` : ''
        const addSurcharge = (key, amount) => {
            // Kalau ada >1 collie yg sama-sama kena surcharge yg sama tanpa
            // label (harusnya tidak terjadi krn label selalu diisi di mode
            // multi-package), jumlahkan alih-alih menimpa.
            surcharges[key] = (surcharges[key] || 0) + amount
        }
        if (weight_kg > 70 || geom.L > 274 || geom.length_plus_girth > 400) {
            addSurcharge(`Over Maximum (OMX)${suffix}`, COSTS_MAY_24_2026.OMX)
            addSurcharge(`Large Package Surcharge (LPS)${suffix}`, COSTS_MAY_24_2026.LPS)
            if (multiPackage) {
                // Floor 40kg berlaku PER COLLIE yg kena OMX/LPS -- naikkan
                // total chargeable weight (dipakai Surge Fee) sebesar selisih
                // collie ini ke 40kg, bukan floor seluruh shipment ke 40kg.
                const pcw = Math.max(weight_kg, (geom.L * geom.W * geom.H) / DIM_DIVISOR)
                adjustedChargeableWeight += Math.max(0, 40 - pcw)
            } else {
                adjustedChargeableWeight = Math.max(adjustedChargeableWeight, 40)
            }
        } else if (geom.length_plus_girth > 300) {
            addSurcharge(`Large Package Surcharge (LPS)${suffix}`, COSTS_MAY_24_2026.LPS)
            if (multiPackage) {
                const pcw = Math.max(weight_kg, (geom.L * geom.W * geom.H) / DIM_DIVISOR)
                adjustedChargeableWeight += Math.max(0, 40 - pcw)
            } else {
                adjustedChargeableWeight = Math.max(adjustedChargeableWeight, 40)
            }
        } else if (
            (weight_kg > 25 && weight_kg < 71) ||
            geom.L > 122 || geom.W > 76 ||
            packagingTriggersAHS(extra || {})
        ) {
            addSurcharge(`Additional Handling (AHS)${suffix}`, COSTS_MAY_24_2026.AHS)
        }
    })

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

    // Layanan tambahan opsional (manual tick) -- lihat surcharges/optional.js.
    // package_count dipakai utk Direct Delivery Only & Carbon Offsets (per
    // package); is_freight dipetakan dari service 'wwef' (analog "UPS
    // Worldwide Express Freight Services" di PDF -- engine ini tidak model
    // Express Freight/Freight Midday scr terpisah dari saver/expedited).
    const optResult = computeOptionalSurcharges(direction, chargeableWeight, {
        is_freight: service === 'wwef',
        package_count: multiPackage ? request.packages.length : 1,
        ...(request.special_handling || {}),
    }, country, postalCode)
    optResult.components.forEach(c => {
        surcharges[c.label] = pyRound(c.amount)
    })
    const notes = [...optResult.notes]

    // Insurance / Declared Value -- lihat surcharges/insurance.js. Terima
    // dari extra.declared_value_idr (dipakai UI ini) ATAU
    // special_handling.declared_value_idr (kalau caller API pakai konvensi
    // itu), yang manapun diisi.
    const declaredValueIdr = request.extra?.declared_value_idr ?? request.special_handling?.declared_value_idr
    if (declaredValueIdr && declaredValueIdr > 0) {
        const ins = computeInsuranceSurcharge(declaredValueIdr)
        if (ins.fee > 0) surcharges['Insurance / Declared Value'] = pyRound(ins.fee)
        notes.push(ins.note)
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
        notes: notes,
        extra: {
            chargeable_weight: chargeableWeight,
            dim_weight: dimWeight,
            country: country,
            surge_region: region
        }
    }
}

export default { calculate }
