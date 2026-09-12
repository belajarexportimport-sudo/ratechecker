/**
 * FedEx Non-Standard Shipment Fees (Porting 1:1 dari nonstandard.py)
 * =================================================================
 * Surcharge berbasis dimensi & flag paket/freight unit.
 *
 * Surcharge Paket (IP / IE):
 * 1. AHS - Dimension         : IDR 431.000
 * 2. AHS - Weight            : IDR 431.000
 * 3. AHS - Packaging         : IDR 431.000
 * 4. Oversize Charge         : IDR 1.072.000
 * 5. Unauthorized Package Chg: IDR 4.447.000
 *
 * Surcharge Freight Unit (IPF / IEF):
 * 6. AHS - Freight           : IDR 2.944.000
 * 7. Non-Stackable Surcharge : IDR 3.700.000
 * 8. Unauthorized Freight Chg: IDR 7.306.000
 */

export const AHS_DIMENSION_FEE = 431000
export const AHS_WEIGHT_FEE = 431000
export const AHS_PACKAGING_FEE = 431000
export const OVERSIZE_FEE = 1072000
export const UNAUTHORIZED_PACKAGE_FEE = 4447000

export const AHS_DIMENSION_MIN_BILLABLE_KG = 18

export const AHS_FREIGHT_FEE = 2944000
export const NON_STACKABLE_FEE = 3700000
export const UNAUTHORIZED_FREIGHT_FEE = 7306000

export const DIMENSIONAL_WEIGHT_DIVISOR_CM = 5000

export const IPIE_MAX_WEIGHT_KG = 68
export const IPIE_MAX_LENGTH_CM = 274
export const IPIE_MAX_LENGTH_PLUS_GIRTH_CM = 330

function _longestAndLengthPlusGirth(length_cm, width_cm, height_cm) {
    // TIDAK di-sort: Length = length_cm apa adanya, Girth = 2*W + 2*H
    const girth = 2 * width_cm + 2 * height_cm
    return {
        longest: length_cm,
        second: width_cm,
        length_plus_girth: length_cm + girth
    }
}

/**
 * Hitung Non-Standard Fee untuk 1 package/collie (IP & IE).
 */
export function checkPackageSurcharge(length_cm, width_cm, height_cm, weight_kg, opts = {}) {
    if (length_cm <= 0 || width_cm <= 0 || height_cm <= 0) {
        throw new Error("Dimensi (length/width/height) harus > 0 cm.")
    }
    if (weight_kg <= 0) {
        throw new Error("weight_kg harus > 0.")
    }

    const { non_cardboard_packaging = false, round_or_cylindrical = false,
            banded_or_has_wheels_handles_straps = false, could_entangle_or_damage = false } = opts

    const { longest, second, length_plus_girth } = _longestAndLengthPlusGirth(length_cm, width_cm, height_cm)
    const volume_cm3 = length_cm * width_cm * height_cm

    const ahs_dimension = (longest > 121 || second > 76 || length_plus_girth > 266 || volume_cm3 > 169901)
    const ahs_weight = weight_kg > 25
    const ahs_packaging = Boolean(non_cardboard_packaging || round_or_cylindrical ||
                            banded_or_has_wheels_handles_straps || could_entangle_or_damage)
    const oversize = (longest > 243 || length_plus_girth > 330 || weight_kg > 50 || volume_cm3 > 283168)
    const unauthorized = (longest > 274 || length_plus_girth > 419 || weight_kg > 68)

    const candidates = []
    if (ahs_dimension) candidates.push({ label: "AHS - Dimension", charge: AHS_DIMENSION_FEE })
    if (ahs_weight) candidates.push({ label: "AHS - Weight", charge: AHS_WEIGHT_FEE })
    if (ahs_packaging) candidates.push({ label: "AHS - Packaging", charge: AHS_PACKAGING_FEE })
    if (oversize) candidates.push({ label: "Oversize Charge", charge: OVERSIZE_FEE })
    if (unauthorized) candidates.push({ label: "Unauthorized Package Charge", charge: UNAUTHORIZED_PACKAGE_FEE })

    if (candidates.length === 0) {
        return {
            triggered: [],
            charge: 0,
            label: null,
            min_billable_weight_kg: null,
            measurements: {
                longest_cm: longest,
                second_longest_cm: second,
                length_plus_girth_cm: length_plus_girth,
                volume_cm3: volume_cm3
            }
        }
    }

    // Aturan FedEx: Ambil yang PALING BESAR (highest charge after discount)
    let best = candidates[0]
    for (const c of candidates) {
        if (c.charge > best.charge) best = c
    }

    return {
        triggered: candidates.map(c => c.label),
        charge: best.charge,
        label: best.label,
        min_billable_weight_kg: ahs_dimension ? AHS_DIMENSION_MIN_BILLABLE_KG : null,
        measurements: {
            longest_cm: longest,
            second_longest_cm: second,
            length_plus_girth_cm: length_plus_girth,
            volume_cm3: volume_cm3
        }
    }
}

/**
 * Hitung Non-Standard Fee untuk 1 freight handling unit (IPF & IEF).
 */
export function checkFreightSurcharge(length_cm, weight_kg, width_cm = null, height_cm = null, non_stackable = false) {
    if (length_cm <= 0) throw new Error("length_cm harus > 0.")
    if (weight_kg <= 0) throw new Error("weight_kg harus > 0.")

    const notes = []
    let length_plus_girth = null
    let longest = length_cm

    if (width_cm != null && height_cm != null) {
        if (width_cm <= 0 || height_cm <= 0) throw new Error("width_cm/height_cm harus > 0 kalau diisi.")
        const calc = _longestAndLengthPlusGirth(length_cm, width_cm, height_cm)
        longest = calc.longest
        length_plus_girth = calc.length_plus_girth
    } else {
        notes.push("width_cm/height_cm tidak diisi -> kriteria length+girth utk Unauthorized Freight Charge di-skip (cek manual kalau unit besar/tidak beraturan).")
    }

    const ahs_freight = longest > 157
    const unauthorized = (longest > 302 || weight_kg > 1995 || (length_plus_girth != null && length_plus_girth > 762))

    const ahs_freight_charge = ahs_freight ? AHS_FREIGHT_FEE : 0
    const non_stackable_charge = non_stackable ? NON_STACKABLE_FEE : 0
    const unauthorized_charge = unauthorized ? UNAUTHORIZED_FREIGHT_FEE : 0

    let charge = 0
    let label = null
    let triggered = []

    if (unauthorized_charge > 0 && (ahs_freight_charge > 0 || non_stackable_charge > 0)) {
        // Jika melibatkan Unauthorized Freight, ambil tertinggi
        const components = []
        if (unauthorized_charge > 0) components.push({ label: "Unauthorized Freight Charge", charge: unauthorized_charge })
        if (ahs_freight_charge > 0) components.push({ label: "AHS - Freight", charge: ahs_freight_charge })
        if (non_stackable_charge > 0) components.push({ label: "Non-Stackable Surcharge", charge: non_stackable_charge })

        let best = components[0]
        for (const c of components) {
            if (c.charge > best.charge) best = c
        }
        charge = best.charge
        label = best.label
        triggered = components.map(c => c.label)
    } else {
        // AHS-Freight + Non-Stackable tanpa Unauthorized → DIJUMLAH
        const parts = []
        if (ahs_freight_charge > 0) parts.push({ label: "AHS - Freight", charge: ahs_freight_charge })
        if (non_stackable_charge > 0) parts.push({ label: "Non-Stackable Surcharge", charge: non_stackable_charge })

        charge = parts.reduce((sum, p) => sum + p.charge, 0)
        triggered = parts.map(p => p.label)
        label = parts.length > 0 ? parts.map(p => p.label).join(" + ") : null
        if (parts.length > 1) {
            notes.push("AHS - Freight dan Non-Stackable Surcharge sama-sama trigger tanpa Unauthorized Freight Charge -> DIJUMLAH (asumsi, karena PDF tidak menyebut aturan 'ambil tertinggi' utk kombinasi spesifik ini). Konfirmasi ke FedEx CS kalau butuh kepastian.")
        }
    }

    return {
        triggered,
        charge,
        label,
        notes,
        measurements: { longest_cm: longest, length_plus_girth_cm: length_plus_girth }
    }
}

/**
 * Dimensional weight (kg) = L x W x H / 5000
 */
export function dimensionalWeightKg(length_cm, width_cm, height_cm, divisor = DIMENSIONAL_WEIGHT_DIVISOR_CM) {
    if (length_cm <= 0 || width_cm <= 0 || height_cm <= 0) {
        throw new Error("Dimensi (length/width/height) harus > 0 cm.")
    }
    return (length_cm * width_cm * height_cm) / divisor
}

/**
 * Hitung CWT shipment IP/IE multi-package.
 */
export function computeShipmentChargeableWeight(packages, divisor = DIMENSIONAL_WEIGHT_DIVISOR_CM) {
    const details = []
    let total = 0.0

    packages.forEach((pkg, i) => {
        const label = pkg.label || `Collie ${i + 1}`
        const { length_cm, width_cm, height_cm, weight_kg: actual } = pkg
        const dim_w = dimensionalWeightKg(length_cm, width_cm, height_cm, divisor)

        const chk = checkPackageSurcharge(length_cm, width_cm, height_cm, actual, pkg)
        const floor = chk.min_billable_weight_kg || 0

        const cw = Math.max(actual, dim_w, floor)
        total += cw
        details.push({
            label,
            actual_weight_kg: actual,
            dimensional_weight_kg: dim_w,
            chargeable_weight_kg: cw,
            ahs_dimension_floor_applied: floor > 0 && cw === floor
        })
    })

    return { total_chargeable_weight_kg: total, details }
}

/**
 * Hitung CWT shipment IPF/IEF multi-unit.
 */
import { MINIMUM_FREIGHT_WEIGHT_KG } from '../rules.js'

export function computeFreightChargeableWeight(freight_units, divisor = DIMENSIONAL_WEIGHT_DIVISOR_CM) {
    const details = []
    let total = 0.0

    freight_units.forEach((unit, i) => {
        const label = unit.label || `Unit ${i + 1}`
        const actual = unit.weight_kg
        const { length_cm, width_cm, height_cm } = unit

        let dim_w = null
        let cw = actual

        if (length_cm != null && width_cm != null && height_cm != null) {
            dim_w = dimensionalWeightKg(length_cm, width_cm, height_cm, divisor)
            cw = Math.max(actual, dim_w)
        }

        // PERBAIKAN (laporan user 12 Sep 2026): IPF/IEF minimum billable
        // weight 68kg/unit TIDAK PERNAH diterapkan di jalur ini -- cuma
        // diterapkan di jalur `else` (single dimensions_cm, bukan lewat
        // auto-switch/freight_units) lewat MINIMUM_FREIGHT_WEIGHT_KG di
        // calculator.js. Akibatnya, shipment yang auto-switch dari IP/IE
        // ke IPF/IEF (mis. dims 52x50x90cm) chargeable weight-nya cuma
        // ~40-an kg (actual/dim mentah), bukan minimum 68kg per PDF FedEx
        // ("A 68kg minimum rate charge per package shall apply to IPF or
        // IEF shipments weighing less than 68kg"). Floor diterapkan PER
        // freight unit (sesuai "per package"), lalu dijumlah.
        cw = Math.max(cw, MINIMUM_FREIGHT_WEIGHT_KG)

        total += cw
        details.push({
            label,
            actual_weight_kg: actual,
            dimensional_weight_kg: dim_w,
            chargeable_weight_kg: cw
        })
    })

    return { total_chargeable_weight_kg: total, details }
}

export function checkServiceEligibility(length_cm, width_cm, height_cm, weight_kg) {
    const { longest, length_plus_girth } = _longestAndLengthPlusGirth(length_cm, width_cm, height_cm)
    const reasons = []

    if (weight_kg >= IPIE_MAX_WEIGHT_KG) {
        reasons.push(`Berat ${weight_kg}kg >= ${IPIE_MAX_WEIGHT_KG}kg`)
    }
    if (longest >= IPIE_MAX_LENGTH_CM) {
        reasons.push(`Panjang ${longest}cm >= ${IPIE_MAX_LENGTH_CM}cm`)
    }
    if (length_plus_girth > IPIE_MAX_LENGTH_PLUS_GIRTH_CM) {
        reasons.push(`Panjang+lilit ${length_plus_girth}cm > ${IPIE_MAX_LENGTH_PLUS_GIRTH_CM}cm`)
    }

    return {
        required: reasons.length > 0,
        reasons,
        measurements: { longest_cm: longest, length_plus_girth_cm: length_plus_girth }
    }
}

// =============================================================================
// PERBAIKAN: evaluatePackagesForServiceSwitch() -- port dari
// evaluate_packages_for_service_switch() Python. checkServiceEligibility()
// di atas SUDAH ADA sejak sebelumnya tapi TIDAK PERNAH DIPANGGIL di
// calculator.js -> auto-switch IP/IE -> IPF/IEF TIDAK PERNAH terjadi di JS
// (dibuktikan: dims 52x50x90cm, length+girth=332cm>330cm, seharusnya WAJIB
// pindah ke IPF/IEF, tapi service tetap "IP"). Fungsi ini + wiring di
// calculator.js memperbaiki itu.
// =============================================================================

export class ShipmentSplitRequired extends Error {
    constructor(message, eligibility) {
        super(message)
        this.name = 'ShipmentSplitRequired'
        this.eligibility = eligibility
    }
}

export function evaluatePackagesForServiceSwitch(service, packages) {
    const eligibility = packages.map((pkg, i) => {
        const elig = checkServiceEligibility(pkg.length_cm, pkg.width_cm, pkg.height_cm, pkg.weight_kg)
        elig.label = pkg.label || `Collie ${i + 1}`
        return elig
    })

    const anyRequired = eligibility.some(e => e.required)
    if (!anyRequired) {
        return { action: 'none', new_service: null, eligibility }
    }

    const allRequired = eligibility.every(e => e.required)
    if (packages.length > 1 && !allRequired) {
        throw new ShipmentSplitRequired(
            `Sebagian collie melebihi batas maksimum ${service.toUpperCase()} ` +
            `(berat >= ${IPIE_MAX_WEIGHT_KG}kg, panjang >= ${IPIE_MAX_LENGTH_CM}cm, ` +
            `atau panjang+lilit > ${IPIE_MAX_LENGTH_PLUS_GIRTH_CM}cm), sementara collie ` +
            `lain masih dalam batas. Satu shipment tidak boleh mencampur service ` +
            `${service.toUpperCase()} dengan IPF/IEF -> pisahkan jadi 2 pengiriman terpisah.`,
            eligibility
        )
    }

    const newService = service.toUpperCase() === 'IP' ? 'IPF' : 'IEF'
    const forcedFeePreview = packages.map((pkg, i) => {
        const chk = checkPackageSurcharge(pkg.length_cm, pkg.width_cm, pkg.height_cm, pkg.weight_kg, pkg)
        return {
            label: eligibility[i].label,
            reasons: eligibility[i].reasons,
            forced_label: chk.label,
            forced_charge: chk.charge,
        }
    })

    return { action: 'switch', new_service: newService, eligibility, forced_fee_preview: forcedFeePreview }
}
