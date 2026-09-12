export const DIM_DIVISOR = 5000;
export const MINIMUM_BILLED_WEIGHT_KG = 0.5;
// PERBAIKAN #5: Freight (IPF/IEF) minimum billable weight = 68kg
export const MINIMUM_FREIGHT_WEIGHT_KG = 68.0;


export const FREIGHT_SERVICES = ["IPF", "IEF"];
export const PARCEL_SERVICES = ["IP", "IE"];

export function isFreight(service) {
    return FREIGHT_SERVICES.includes(service.toUpperCase());
}

export function calculateDimWeight(length, width, height) {
    if (!length || !width || !height) return 0;
    return (length * width * height) / DIM_DIVISOR;
}

export function roundUp1000(amount) {
    return Math.ceil(amount / 1000) * 1000;
}

// === Declared Value Charge for Carriage ===
// FedEx Surcharge and Other Information -- Indonesia (ID_20260629_180258),
// hal. 3: "the declared value surcharge for Export and ImportOne shipments
// paid by Indonesia customers is equal to IDR 34,000 per IDR 1,375,000 (or
// fraction thereof) by which the declared value for carriage exceeds the
// greater of: (i) IDR 1,375,000 or (ii) IDR 125,000 per pound."
//
// PENTING -- ini beda dari UPS Additional Insurance: ada KOMPONEN BERAT.
// Ambang bebas biaya bukan flat IDR1.375.000, tapi mana yang LEBIH BESAR
// antara IDR1.375.000 vs (berat dalam pound x IDR125.000). Utk shipment
// berat, ambang bebasnya jadi lebih tinggi dari IDR1.375.000.
export const DECLARED_VALUE_BASE_THRESHOLD = 1375000;
export const DECLARED_VALUE_PER_LB_THRESHOLD = 125000;
export const DECLARED_VALUE_INCREMENT = 1375000;
export const DECLARED_VALUE_RATE_PER_INCREMENT = 34000;
export const KG_TO_LB = 2.20462;

// Batas maksimum declared value (informasional -- utk validasi/warning, tidak
// menghitung biaya). Dalam USD, dikonversi sesuai kurs yg dipakai user kalau
// perlu ditampilkan; di sini disimpan mentah dalam USD.
export const MAX_DECLARED_VALUE_USD = {
    envelope_pak: 100,
    ip_ie: 50000,
    ipf_ief: 100000,
};

// weightKg: berat AKTUAL shipment (bukan chargeable/billed weight -- PDF
// menyebut "per pound" tanpa menyebut "chargeable", jadi dipakai berat aktual).
export function computeDeclaredValueCharge(declaredValueIdr, weightKg) {
    if (!declaredValueIdr || declaredValueIdr <= 0) return 0;
    const weightLb = (weightKg || 0) * KG_TO_LB;
    const threshold = Math.max(DECLARED_VALUE_BASE_THRESHOLD, weightLb * DECLARED_VALUE_PER_LB_THRESHOLD);
    if (declaredValueIdr <= threshold) return 0;
    const excess = declaredValueIdr - threshold;
    const units = Math.ceil(excess / DECLARED_VALUE_INCREMENT);
    return units * DECLARED_VALUE_RATE_PER_INCREMENT;
}
