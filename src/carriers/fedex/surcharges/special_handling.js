/**
 * FedEx Special Handling Fees (Porting 1:1 dari special_handling.py)
 * =================================================================
 * Memuat semua tarif & kriteria surcharge opsional/layanan khusus FedEx:
 * - Address Correction: IDR 187.000
 * - Third Party Consignee Surcharge: IDR 163.000
 * - International Broker Select: Min IDR 163.000 / IDR 19.000 per kg
 * - Saturday Pick Up: IDR 250.000
 * - Saturday Delivery: IDR 250.000
 * - Inbound Processing Fee: IDR 44.000 (US & EU export)
 * - ISR (Indirect Signature Required): IDR 53.000 (Non-freight)
 * - DSR (Direct Signature Required): IDR 59.000 (Non-freight)
 * - ASR (Adult Signature Required): IDR 75.000 (Non-freight)
 * - Residential Delivery Surcharge: IDR 55.000 (Non-freight) / IDR 1.772.000 (Freight) - US & Canada only, mutually exclusive dengan ODA
 * - Accessible Dangerous Goods: Min IDR 1.890.000 / IDR 34.000 per kg
 * - Inaccessible Dangerous Goods: Min IDR 885.000 / IDR 13.000 per kg
 * - Dry Ice Surcharge: IDR 82.000 (bila tidak ada DG)
 * - Third Party Billing Surcharge: 2.5% dari (base rate + net freight charges)
 */

export const EU_MEMBER_STATES = new Set([
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech republic",
    "denmark", "estonia", "finland", "france", "germany", "greece", "hungary",
    "ireland", "italy", "latvia", "lithuania", "luxembourg", "malta",
    "netherlands", "poland", "portugal", "romania", "slovak republic",
    "slovenia", "spain", "sweden"
])

export const ADDRESS_CORRECTION_FEE = 187000
export const THIRD_PARTY_CONSIGNEE_FEE = 163000
export const BROKER_SELECT_MIN_FEE = 163000
export const BROKER_SELECT_PER_KG = 19000
export const SATURDAY_PICKUP_FEE = 250000
export const SATURDAY_DELIVERY_FEE = 250000
export const INBOUND_PROCESSING_FEE = 44000
export const ISR_FEE = 53000
export const DSR_FEE = 59000
export const ASR_FEE = 75000
export const RESIDENTIAL_NON_FREIGHT_FEE = 55000
export const RESIDENTIAL_FREIGHT_FEE = 1772000
export const ACCESSIBLE_DG_MIN_FEE = 1890000
export const ACCESSIBLE_DG_PER_KG = 34000
export const INACCESSIBLE_DG_MIN_FEE = 885000
export const INACCESSIBLE_DG_PER_KG = 13000
export const DRY_ICE_FEE = 82000

export const THIRD_PARTY_BILLING_PCT = 2.5

// --- Declared Value Charge for Carriage (Asuransi) ---
// Sumber: fedex-rates-sur-en-id-2026.pdf hal.3.
// Liability standar FedEx dibatasi pada yg LEBIH BESAR antara USD20/kg
// atau USD100/shipment (dlm ekivalen IDR). Kalau nilai barang (declared
// value) melebihi batas itu, dikenakan "declared value surcharge":
// IDR34.000 per kelipatan IDR1.375.000 (atau sebagian) dari SELISIH nilai
// barang thd batas yg lebih besar antara IDR1.375.000 ATAU IDR125.000/pound
// berat billable.
export const DECLARED_VALUE_INCREMENT_IDR = 1375000
export const DECLARED_VALUE_SURCHARGE_PER_INCREMENT_FEE = 34000
export const DECLARED_VALUE_PER_LB_THRESHOLD_IDR = 125000
export const KG_TO_LB = 2.20462262

export function isUsOrEuDestination(direction, country) {
    if (direction !== "export") return false
    const c = country.trim().toLowerCase()
    if (c.startsWith("united states")) return true
    return EU_MEMBER_STATES.has(c)
}

export function isUsOrCanada(country) {
    const c = country.strip ? country.strip().toLowerCase() : country.trim().toLowerCase()
    return c.startsWith("united states") || c === "canada"
}

export function computeSpecialHandling(service, direction, country, billed_weight_kg, opts = {}) {
    const {
        oda_applied = false,
        address_correction = false,
        third_party_consignee = false,
        broker_select = false,
        saturday_pickup = false,
        saturday_delivery = false,
        isr = false, dsr = false, asr = false,
        residential = false,
        accessible_dangerous_goods = false,
        inaccessible_dangerous_goods = false,
        dry_ice = false,
        inbound_processing_fee_override = null,
        declared_value_idr = 0,
    } = opts

    const is_freight = ["IPF", "IEF"].includes(service.toUpperCase())
    const components = []
    const notes = []

    if (address_correction) {
        components.push({ label: "Address Correction", amount: ADDRESS_CORRECTION_FEE })
    }

    if (third_party_consignee) {
        components.push({ label: "Third Party Consignee Surcharge", amount: THIRD_PARTY_CONSIGNEE_FEE })
    }

    if (broker_select) {
        const charge = Math.max(BROKER_SELECT_MIN_FEE, BROKER_SELECT_PER_KG * billed_weight_kg)
        components.push({ label: "FedEx International Broker Select", amount: charge })
    }

    if (saturday_pickup) {
        components.push({ label: "Saturday Pick Up", amount: SATURDAY_PICKUP_FEE })
    }

    if (saturday_delivery) {
        components.push({ label: "Saturday Delivery", amount: SATURDAY_DELIVERY_FEE })
    }

    const inbound_applicable = inbound_processing_fee_override !== null
        ? inbound_processing_fee_override
        : isUsOrEuDestination(direction, country)

    if (inbound_applicable) {
        components.push({ label: "Inbound Processing Fee", amount: INBOUND_PROCESSING_FEE })
    }

    const sigs = [
        { flag: isr, label: "Indirect Signature Required (ISR)", fee: ISR_FEE },
        { flag: dsr, label: "Direct Signature Required (DSR)", fee: DSR_FEE },
        { flag: asr, label: "Adult Signature Required (ASR)", fee: ASR_FEE }
    ]

    sigs.forEach(({ flag, label, fee }) => {
        if (!flag) return
        if (is_freight) {
            notes.push(`${label} hanya berlaku utk non-freight (IP/IE) -> diabaikan untuk ${service.toUpperCase()}.`)
        } else {
            components.push({ label, amount: fee })
        }
    })

    if (residential) {
        if (!isUsOrCanada(country)) {
            notes.push(`Residential Delivery Surcharge hanya berlaku utk destinasi US & Canada -> diabaikan (destinasi saat ini: ${country}).`)
        } else if (oda_applied) {
            notes.push("ODA Surcharge sudah diterapkan pada shipment ini -> Residential Delivery Surcharge TIDAK dibebankan (mutually exclusive, sesuai aturan FedEx).")
        } else {
            const charge = is_freight ? RESIDENTIAL_FREIGHT_FEE : RESIDENTIAL_NON_FREIGHT_FEE
            components.push({ label: "Residential Delivery Surcharge", amount: charge })
        }
    }

    let dg_present = false
    if (accessible_dangerous_goods) {
        const charge = Math.max(ACCESSIBLE_DG_MIN_FEE, ACCESSIBLE_DG_PER_KG * billed_weight_kg)
        components.push({ label: "Accessible Dangerous Goods", amount: charge })
        dg_present = true
    }

    if (inaccessible_dangerous_goods) {
        const charge = Math.max(INACCESSIBLE_DG_MIN_FEE, INACCESSIBLE_DG_PER_KG * billed_weight_kg)
        components.push({ label: "Inaccessible Dangerous Goods", amount: charge })
        dg_present = true
    }

    if (accessible_dangerous_goods && inaccessible_dangerous_goods) {
        notes.push("Accessible & Inaccessible Dangerous Goods sama-sama ditandai -> kedua surcharge DIJUMLAH (asumsi utk 2 jenis barang berbeda dalam 1 AWB; PDF tidak eksplisit atur kombinasi ini, konfirmasi ke FedEx CS kalau perlu pasti).")
    }

    if (dg_present) {
        notes.push("Dangerous Goods surcharge hanya berlaku utk shipment dgn origin/destination di Great Jakarta atau Batam -> pastikan kondisi ini terpenuhi (TIDAK divalidasi otomatis di sini).")
    }

    if (dry_ice) {
        if (dg_present) {
            notes.push("Dangerous Goods surcharge sudah diterapkan -> Dry Ice Surcharge TIDAK dibebankan (sesuai aturan FedEx: DG + dry ice bareng, cuma DG surcharge yang berlaku).")
        } else {
            components.push({ label: "Dry Ice Surcharge", amount: DRY_ICE_FEE })
        }
    }

    // --- Declared Value Charge for Carriage (Asuransi) ---
    if (declared_value_idr > 0) {
        const weightLb = billed_weight_kg * KG_TO_LB
        const threshold = Math.max(DECLARED_VALUE_INCREMENT_IDR, DECLARED_VALUE_PER_LB_THRESHOLD_IDR * weightLb)
        if (declared_value_idr > threshold) {
            const excess = declared_value_idr - threshold
            const increments = Math.ceil(excess / DECLARED_VALUE_INCREMENT_IDR)
            components.push({ label: "Declared Value Charge for Carriage", amount: increments * DECLARED_VALUE_SURCHARGE_PER_INCREMENT_FEE })
        } else {
            notes.push(`Nilai barang (IDR${declared_value_idr.toLocaleString('id-ID')}) belum melebihi batas liabilitas standar FedEx (IDR${Math.round(threshold).toLocaleString('id-ID')}, dihitung dari berat billable ${billed_weight_kg}kg) -- tidak ada declared value surcharge.`)
        }
    }

    const total = components.reduce((sum, c) => sum + c.amount, 0)

    return {
        components,
        total_charge: total,
        notes
    }
}
