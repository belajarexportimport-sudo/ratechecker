/**
 * Skema Handling Fee / ancillary clearance fee UPS -- di-porting PERSIS
 * dari `calculator-ups/script.js` (proyek kalkulator UPS milik user).
 *
 * Diekstrak dari `duty_tax/calculator.js` (sebelumnya inline di sana) supaya
 * konsisten dengan prinsip carrier isolation di PRD: skema ancillary fee
 * FedEx (lihat handling_fedex.js) beda total strukturnya dari UPS, jadi
 * masing-masing punya "dunia" sendiri -- yang di-share cuma core duty/tax
 * (Bea Masuk/PPN/PPh) di calculator.js, BUKAN skema handling fee-nya.
 */

export const HANDLING_FEE_MIN = 200000
export const HANDLING_FEE_PCT = 0.025
export const DISBURSEMENT_FEE_MIN = 94159
export const DISBURSEMENT_FEE_PCT = 0.059
export const STORAGE_FEE_PER_KG_PER_DAY = 3016
export const STORAGE_FEE_MIN_DAYS = 3
export const DEFAULT_DOC_FEE_IDR = 50000

/**
 * @param {number} totalTaxNoHandling - Bea Masuk + PPN + PPh (sebelum handling)
 * @param {Object} handling - { enabled, doc_fee_idr, warehouse_days, weight_kg }
 * @returns {Object|null} breakdown, atau null kalau totalTaxNoHandling <= 0
 */
export function computeUpsHandlingFees(totalTaxNoHandling, handling = {}) {
    if (totalTaxNoHandling <= 0) return null

    const suggestedHandlingFee = Math.max(HANDLING_FEE_MIN, Math.ceil(totalTaxNoHandling * HANDLING_FEE_PCT))
    const suggestedDisbursementFee = Math.max(DISBURSEMENT_FEE_MIN, Math.ceil(totalTaxNoHandling * DISBURSEMENT_FEE_PCT))

    if (!handling.enabled) {
        return {
            enabled: false,
            handling_fee_idr: suggestedHandlingFee,
            disbursement_fee_idr: suggestedDisbursementFee,
            doc_fee_idr: 0,
            warehouse_days: 0,
            storage_fee_idr: 0,
            total_handling_idr: 0,
            notes: ['Handling Fee & Disbursement Fee di atas cuma SARAN (belum dimasukkan ke total) -- aktifkan "Hitung Import Handling" utk memasukkannya ke total.'],
        }
    }

    const docFee = handling.doc_fee_idr != null ? handling.doc_fee_idr : DEFAULT_DOC_FEE_IDR
    const whDays = handling.warehouse_days || 0
    const weightKg = handling.weight_kg || 0
    const storageFee = whDays >= STORAGE_FEE_MIN_DAYS
        ? Math.ceil(STORAGE_FEE_PER_KG_PER_DAY * weightKg * whDays)
        : 0
    const totalHandling = suggestedHandlingFee + suggestedDisbursementFee + docFee + storageFee

    return {
        enabled: true,
        handling_fee_idr: suggestedHandlingFee,
        disbursement_fee_idr: suggestedDisbursementFee,
        doc_fee_idr: docFee,
        warehouse_days: whDays,
        storage_fee_idr: storageFee,
        total_handling_idr: totalHandling,
        notes: [],
    }
}

export const SUGGESTED_WAREHOUSE_DAYS = STORAGE_FEE_MIN_DAYS
