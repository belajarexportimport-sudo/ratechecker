/**
 * Skema ancillary clearance service fees FedEx -- sumber:
 * "Clearance services and related fees FDX ID.docx" (dilampirkan user).
 *
 * BERBEDA dari skema UPS (lihat handling_ups.js) -- FedEx punya lebih banyak
 * line-item terpisah (bukan cuma Handling Fee + Disbursement Fee flat),
 * dan skema Storage Fee-nya beda per JENIS ENTRY (PIBK/PIB/BC2.3), bukan
 * satu aturan generik. Core duty/tax (Bea Masuk/PPN/PPh) di calculator.js
 * TETAP SAMA dgn UPS -- yang beda cuma ancillary fee di modul ini.
 *
 * Cakupan (6 baris tabel docx):
 *   1. Storage / Warehouse Fee      -- 3 varian: PIBK+CN, PIB, BC2.3
 *   2. Processing Fee (Admin Fee)   -- tiered by D&T
 *   3. Broker Document Transfer     -- opsional, flat/shipment
 *   4. Disbursement Fee             -- tiered by D&T
 *   5. Export Formal Clearance      -- opsional, EXPORT only, flat/shipment
 *   6. Duty and Tax Forwarding Fee  -- ALTERNATIF Disbursement Fee (saling
 *                                      eksklusif, dipilih kalau billing pihak
 *                                      ketiga di luar negara tujuan)
 *
 * "Applicable ancillary clearance service fees are subject to VAT/GST" ->
 * PPN 11% (PPN_RATE, sama dgn tarif di calculator.js) ditambahkan di atas
 * SUBTOTAL semua ancillary fee yang benar-benar ke-charge di bawah ini.
 */

import { PPN_RATE } from './constants.js'

// --- 1. Storage / Warehouse Fee ---
export const STORAGE_PER_SHIPMENT_PER_DAY_IDR = 2500
export const STORAGE_PER_KG_PER_DAY_IDR = 2000
export const STORAGE_FREE_DAYS = 3 // hanya berlaku utk PIBK & BC2.3, TIDAK utk PIB (lihat di bawah)

export const ENTRY_TYPES = {
    PIBK: 'pibk',   // PIBK / Simplified Formal Entry / consignment note "CN" -> free hari 1-3
    PIB: 'pib',     // PIB / Formal Entry -> TIDAK ada masa bebas, kena sejak hari 1
    BC23: 'bc23',   // BC2.3 / Bonded Zone -> free hari 1-3
}

/**
 * @param {'pibk'|'pib'|'bc23'} entryType
 * @param {number} warehouseDays - total hari barang menginap di gudang
 * @param {number} weightKg
 */
export function computeFedexStorageFee(entryType, warehouseDays, weightKg) {
    const days = Math.max(0, warehouseDays || 0)
    const weight = Math.max(0, weightKg || 0)

    // PIB (Formal Entry) TIDAK punya masa bebas -- dikenakan sejak hari 1.
    // PIBK (Simplified/CN) & BC2.3 (Bonded Zone) -- gratis hari 1-3, baru
    // dikenakan mulai hari ke-4.
    const billableDays = entryType === ENTRY_TYPES.PIB
        ? days
        : Math.max(0, days - STORAGE_FREE_DAYS)

    const dailyRate = STORAGE_PER_SHIPMENT_PER_DAY_IDR + (STORAGE_PER_KG_PER_DAY_IDR * weight)
    const fee = billableDays > 0 ? Math.ceil(dailyRate * billableDays) : 0

    return {
        entry_type: entryType,
        warehouse_days: days,
        billable_days: billableDays,
        free_days_applied: entryType !== ENTRY_TYPES.PIB ? STORAGE_FREE_DAYS : 0,
        weight_kg: weight,
        daily_rate_idr: Math.ceil(dailyRate),
        storage_fee_idr: fee,
    }
}

// --- 2. Processing Fee (Administration Fee) ---
// Docx: D&T <= 15.000 = gratis; D&T 15.000-250.000 = gratis; D&T > 250.000
// = IDR 50.000. Dua baris pertama tumpang tindih & sama-sama "gratis" ->
// disederhanakan jadi 1 threshold: D&T <= 250.000 gratis, di atasnya flat 50rb.
export const PROCESSING_FEE_THRESHOLD_IDR = 250000
export const PROCESSING_FEE_IDR = 50000

export function computeProcessingFee(dutyTaxIdr) {
    return dutyTaxIdr > PROCESSING_FEE_THRESHOLD_IDR ? PROCESSING_FEE_IDR : 0
}

// --- 3. Broker Document Transfer (opsional -- self-clear pakai broker sendiri) ---
export const BROKER_DOCUMENT_TRANSFER_FEE_IDR = 450000

// --- 4. Disbursement Fee (Duty and Tax Advancement Fee) ---
export const DISBURSEMENT_THRESHOLD_IDR = 250000
export const DISBURSEMENT_FLAT_UNDER_THRESHOLD_IDR = 60000
export const DISBURSEMENT_PCT_OVER_THRESHOLD = 0.025
export const DISBURSEMENT_MIN_OVER_THRESHOLD_IDR = 150000

export function computeDisbursementFee(dutyTaxIdr) {
    if (dutyTaxIdr <= DISBURSEMENT_THRESHOLD_IDR) {
        return DISBURSEMENT_FLAT_UNDER_THRESHOLD_IDR
    }
    return Math.max(DISBURSEMENT_MIN_OVER_THRESHOLD_IDR, Math.ceil(dutyTaxIdr * DISBURSEMENT_PCT_OVER_THRESHOLD))
}

// --- 5. Export Formal Clearance (opsional, EXPORT saja -- Single PEB Declaration) ---
export const EXPORT_FORMAL_CLEARANCE_FEE_IDR = 90000

// --- 6. Duty and Tax Forwarding Fee (ALTERNATIF Disbursement Fee) ---
export const DUTY_TAX_FORWARDING_MIN_IDR = 290000
export const DUTY_TAX_FORWARDING_PCT = 0.025

export function computeDutyTaxForwardingFee(dutyTaxIdr) {
    return Math.max(DUTY_TAX_FORWARDING_MIN_IDR, Math.ceil(dutyTaxIdr * DUTY_TAX_FORWARDING_PCT))
}

/**
 * Hitung SEMUA ancillary clearance fee FedEx sekaligus.
 *
 * @param {number} totalTaxNoHandling - Bea Masuk + PPN + PPh (= "D&T" di docx)
 * @param {Object} opts
 * @param {boolean} [opts.enabled=false] - kalau false, semua fee di bawah
 *   cuma SARAN (tidak masuk total) -- konsisten dgn pola UPS
 *   ("Hitung Import Handling" toggle).
 * @param {'pibk'|'pib'|'bc23'} [opts.entry_type='pibk']
 * @param {number} [opts.warehouse_days=0]
 * @param {number} [opts.weight_kg=0]
 * @param {boolean} [opts.use_broker_document_transfer=false] - opsional,
 *   shipper pilih self-clear pakai broker sendiri.
 * @param {boolean} [opts.use_duty_tax_forwarding=false] - kalau true,
 *   GANTIKAN Disbursement Fee (saling eksklusif, sesuai docx: "will apply
 *   INSTEAD OF the Disbursement Fee").
 * @param {boolean} [opts.export_formal_clearance=false] - opsional, cuma
 *   relevan utk shipment EXPORT yang butuh deklarasi PEB formal.
 */
export function computeFedexClearanceFees(totalTaxNoHandling, opts = {}) {
    const dt = totalTaxNoHandling || 0
    const {
        enabled = false,
        entry_type = ENTRY_TYPES.PIBK,
        warehouse_days = 0,
        weight_kg = 0,
        use_broker_document_transfer = false,
        use_duty_tax_forwarding = false,
        export_formal_clearance = false,
    } = opts

    if (dt <= 0) return null

    const notes = []

    const processingFee = computeProcessingFee(dt)

    // Disbursement Fee & Duty and Tax Forwarding Fee SALING EKSKLUSIF --
    // docx eksplisit: "Duty and Tax Forwarding Fee will apply INSTEAD OF
    // the Disbursement Fee if the shipper selects a third party billing
    // option ...".
    let disbursementFee = 0
    let dutyTaxForwardingFee = 0
    if (use_duty_tax_forwarding) {
        dutyTaxForwardingFee = computeDutyTaxForwardingFee(dt)
        notes.push('Duty and Tax Forwarding Fee dipakai (menggantikan Disbursement Fee) karena billing pihak ketiga di luar negara tujuan dipilih.')
    } else {
        disbursementFee = computeDisbursementFee(dt)
    }

    const storage = computeFedexStorageFee(entry_type, warehouse_days, weight_kg)
    const brokerDocFee = use_broker_document_transfer ? BROKER_DOCUMENT_TRANSFER_FEE_IDR : 0
    const exportClearanceFee = export_formal_clearance ? EXPORT_FORMAL_CLEARANCE_FEE_IDR : 0

    const subtotal = processingFee + disbursementFee + dutyTaxForwardingFee +
        storage.storage_fee_idr + brokerDocFee + exportClearanceFee

    if (!enabled) {
        return {
            enabled: false,
            entry_type,
            processing_fee_idr: processingFee,
            disbursement_fee_idr: disbursementFee,
            duty_tax_forwarding_fee_idr: dutyTaxForwardingFee,
            storage,
            broker_document_transfer_idr: brokerDocFee,
            export_formal_clearance_idr: exportClearanceFee,
            subtotal_idr: subtotal,
            vat_idr: 0,
            total_clearance_fees_idr: 0,
            notes: [...notes, 'Semua ancillary clearance fee di atas cuma SARAN (belum dimasukkan ke total) -- aktifkan "Hitung Import Handling" utk memasukkannya ke total.'],
        }
    }

    // "Applicable ancillary clearance service fees are subject to VAT/GST"
    const vat = Math.round(subtotal * PPN_RATE)
    const total = subtotal + vat

    return {
        enabled: true,
        entry_type,
        processing_fee_idr: processingFee,
        disbursement_fee_idr: disbursementFee,
        duty_tax_forwarding_fee_idr: dutyTaxForwardingFee,
        storage,
        broker_document_transfer_idr: brokerDocFee,
        export_formal_clearance_idr: exportClearanceFee,
        subtotal_idr: subtotal,
        vat_idr: vat,
        total_clearance_fees_idr: total,
        notes,
    }
}
