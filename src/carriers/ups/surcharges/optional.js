/**
 * UPS Optional / "Tickable" Surcharges (Indonesia)
 * =================================================
 * Sumber: 2026 UPS Rate and Service Guide - Indonesia (efektif 7 Jun 2026),
 * halaman 4-8 ("Services with Additional Charges" & "Other Additional Charges").
 *
 * Semua surcharge di file ini BUKAN dihitung otomatis oleh sistem UPS
 * berdasarkan berat/dimensi (beda dgn AHS/LPS/OMX/Brokerage/IPF/Surge Fee
 * yang sudah ada di rules.js & calculator.js) -- surcharge2 ini baru
 * berlaku KALAU pengirim benar2 memilih/memicu layanan tsb (mis. minta
 * PEB/formal declaration, minta Saturday Delivery, dsb). Makanya di UI
 * dibuat sbg checkbox yg "tinggal di-tick" oleh user, bukan dihitung
 * silent oleh engine.
 *
 * Catatan umum:
 * - Semua angka exclusive PPN 1.1% (VAT dikenakan di calculator.js
 *   spt surcharge lain, setelah semua komponen di sini dijumlah).
 * - "per shipment" diasumsikan 1x per perhitungan (kalkulator ini
 *   memodelkan 1 shipment per submit form), KECUALI disebutkan
 *   eksplisit "per package"/"per pallet" -> dikalikan packageCount.
 */

// --- Export/Import Declaration (a.k.a. PEB/PIB) ---
export const EXPORT_DECLARATION_FEE = 190189   // "Export Declaration Surcharge" (PEB) - hal.6
export const IMPORT_DECLARATION_FEE = 190977   // "Import Declaration Surcharge" (PIB) - hal.7

// --- Saturday ---
export const SATURDAY_DELIVERY_NON_FREIGHT_FEE = 171680   // hal.5
export const SATURDAY_DELIVERY_FREIGHT_FEE = 3432120      // WWEF - hal.5

// --- Delivery options ---
export const DIRECT_DELIVERY_ONLY_PER_PKG_FEE = 31080     // hal.5

// --- Area surcharges (Residential/Extended/Remote) ---
export const RESIDENTIAL_NON_FREIGHT_FEE = 58312          // hal.6
export const RESIDENTIAL_FREIGHT_FEE = 1879600            // WWEF - hal.6
export const EXTENDED_AREA_MIN_FEE = 429792                // hal.6
export const EXTENDED_AREA_PER_KG_FEE = 8288
export const REMOTE_AREA_MIN_FEE = 479964                  // hal.6
export const REMOTE_AREA_PER_KG_FEE = 9472

// --- Billing / admin ---
export const DUTY_TAX_FORWARDING_FEE = 310060              // hal.6
export const ADDRESS_CORRECTION_PER_PKG_FEE = 187072        // hal.6
export const ADDRESS_CORRECTION_MAX_PER_SHIPMENT_FEE = 653420
export const BILL_RECEIVER_REFUSAL_FEE = 311980            // hal.6
export const LOOKUP_SURCHARGE_FEE = 15540                  // hal.6
export const REBILL_FEE = 312280                           // hal.6
export const DOCUMENT_FEE = 50000                           // hal.6
export const POST_ENTRY_CLEARANCE_FEE = 100000              // hal.6
export const TEMP_IMPORT_EXPORT_CLEARANCE_FEE = 715000      // hal.6
export const ALTERNATE_BROKER_FEE = 429502                  // hal.6
export const DISBURSEMENT_FEE_MIN = 94159                   // hal.6 (atau 5.9% dr duty/tax, mana yg lebih besar)
export const DISBURSEMENT_FEE_PCT = 5.9

// --- Signature ---
export const DELIVERY_CONFIRMATION_SIGNATURE_FEE = 37740    // hal.7
export const DELIVERY_CONFIRMATION_ADULT_SIGNATURE_FEE = 71040 // hal.7

// --- UPS Import Control ---
export const IMPORT_CONTROL_PRINT_LABEL_FEE = 15540          // hal.8
export const IMPORT_CONTROL_ELECTRONIC_LABEL_FEE = 23380     // hal.8

// --- Sustainability / special cargo ---
export const CARBON_OFFSET_PER_PACKAGE_FEE = 11690           // hal.8
export const CARBON_OFFSET_PER_PALLET_FREIGHT_FEE = 311980   // WWEF - hal.8
export const DRY_ICE_FEE = 78000                              // per package/pallet - hal.4

// --- Freight (WWEF) only ---
export const DELIVERY_REATTEMPT_FREIGHT_FEE = 748800          // hal.8

// --- Compliance / exceptions ---
export const PROHIBITED_ITEM_FEE_PER_PKG = 4440000            // hal.8
export const PAPER_COMMERCIAL_INVOICE_FEE = 370000            // maksimum per shipment - hal.8
export const PRE_RELEASE_NOTIFICATION_FEE = 370000            // hal.8

// --- Additional Insurance ---
export const ADDITIONAL_INSURANCE_THRESHOLD_IDR = 1480000     // hal.5
export const ADDITIONAL_INSURANCE_PER_INCREMENT_FEE = 32710   // per kelipatan threshold di atas

/**
 * Hitung semua surcharge opsional (checkbox) UPS yang di-tick user.
 *
 * @param {Object} params
 * @param {string} params.service - 'envelope' | 'express' | 'saver' | 'expedited' | 'wwef' | dst.
 * @param {string} params.direction - 'export' | 'import'
 * @param {number} params.billedWeightKg - berat billable (chargeable weight) shipment.
 * @param {number} [params.packageCount=1] - jumlah collie/package dlm shipment (utk surcharge per-package).
 * @param {Object} [opts] - flag checkbox dari form (semua default false).
 * @returns {{components: Array<{label:string, amount:number}>, notes: string[]}}
 */
export function computeOptionalUpsSurcharges(params, opts = {}) {
    const {
        service = '',
        direction = 'export',
        billedWeightKg = 0,
        packageCount = 1,
    } = params

    const {
        export_declaration = false,        // PEB
        import_declaration = false,        // PIB
        saturday_delivery = false,
        direct_delivery_only = false,
        residential = false,
        extended_area = false,
        remote_area = false,
        duty_tax_forwarding = false,
        address_correction = false,
        bill_receiver_refusal = false,
        lookup_surcharge = false,
        rebill_fee = false,
        delivery_confirmation_signature = false,
        delivery_confirmation_adult_signature = false,
        document_fee = false,
        post_entry_clearance = false,
        temporary_import_export_clearance = false,
        alternate_broker = false,
        import_control_print_label = false,
        import_control_electronic_label = false,
        carbon_offset = false,
        dry_ice = false,
        delivery_reattempt = false,
        prohibited_item = false,
        paper_commercial_invoice = false,
        pre_release_notification = false,
        disbursement_fee = false,
        duty_tax_amount = 0,               // dipakai kalau disbursement_fee = true
        declared_value_idr = 0,            // nilai barang -> dipakai utk Additional Insurance
    } = opts

    const isFreight = service === 'wwef'
    const isImport = direction === 'import'
    const components = []
    const notes = []
    const addFee = (label, amount) => components.push({ label, amount })

    // --- PEB / PIB ---
    // PENTING: nama "PEB"/"PIB" di sini cuma label pendekatan yg umum
    // dipakai forwarder Indonesia -- surcharge ASLI di UPS guide (hal.6-7)
    // BUKAN dikenakan rutin di setiap ekspor/impor. Syaratnya SALAH SATU:
    // (a) barang termasuk strategic/controlled/regulated goods, ATAU
    // (b) shipper/consignee MEMINTA formal declaration padahal secara
    // hukum tidak wajib. PIB/PEB rutin (yg wajib di setiap shipment)
    // sudah masuk "Customs Brokerage Charges" (gratis s/d 5 tariff line)
    // & "Brokerage Admin Fee (BAF)" IDR118.647 yg SUDAH otomatis
    // dikenakan ke semua impor dutiable (lihat calculator.js -> surcharges['Brokerage']).
    // Jangan asumsikan checkbox ini = "PIB wajib tiap impor".
    if (export_declaration) {
        if (isImport) notes.push('Export Declaration Surcharge (mirip PEB) biasanya berlaku utk shipment EKSPOR, tapi tetap dibebankan sesuai pilihan user.')
        notes.push('Export Declaration Surcharge HANYA berlaku kalau barang termasuk strategic/controlled/regulated goods, ATAU shipper/consignee minta formal declaration walau tidak wajib -- BUKAN biaya rutin di setiap ekspor.')
        addFee('Export Declaration Surcharge (mirip PEB)', EXPORT_DECLARATION_FEE)
    }
    if (import_declaration) {
        if (!isImport) notes.push('Import Declaration Surcharge (mirip PIB) biasanya berlaku utk shipment IMPOR, tapi tetap dibebankan sesuai pilihan user.')
        notes.push('Import Declaration Surcharge HANYA berlaku kalau barang termasuk strategic/controlled/regulated goods, ATAU shipper/consignee minta formal declaration walau tidak wajib -- BUKAN pengganti PIB rutin (PIB rutin & Brokerage Admin Fee/BAF sudah otomatis masuk di baris "Brokerage").')
        addFee('Import Declaration Surcharge (mirip PIB)', IMPORT_DECLARATION_FEE)
    }

    // --- Saturday Delivery ---
    if (saturday_delivery) {
        addFee('Saturday Delivery', isFreight ? SATURDAY_DELIVERY_FREIGHT_FEE : SATURDAY_DELIVERY_NON_FREIGHT_FEE)
    }

    // --- Direct Delivery Only (per package) ---
    if (direct_delivery_only) {
        addFee('Direct Delivery Only', DIRECT_DELIVERY_ONLY_PER_PKG_FEE * Math.max(1, packageCount))
    }

    // --- Residential / Extended Area / Remote Area ---
    if (residential) {
        addFee('Residential Surcharge', isFreight ? RESIDENTIAL_FREIGHT_FEE : RESIDENTIAL_NON_FREIGHT_FEE)
    }
    if (extended_area) {
        addFee('Extended Area Surcharge (DAS)', Math.max(EXTENDED_AREA_MIN_FEE, EXTENDED_AREA_PER_KG_FEE * billedWeightKg))
    }
    if (remote_area) {
        addFee('Remote Area Surcharge', Math.max(REMOTE_AREA_MIN_FEE, REMOTE_AREA_PER_KG_FEE * billedWeightKg))
    }
    if (extended_area && remote_area) {
        notes.push('Extended Area & Remote Area sama-sama ditandai -- pada praktiknya UPS biasanya hanya menerapkan SALAH SATU (tergantung titik alamat), tapi di sini keduanya dijumlah sesuai pilihan user. Cek titik ODA/Remote resmi di ups.com/id kalau perlu pasti.')
    }

    // --- Billing / admin ---
    if (duty_tax_forwarding) addFee('Duty/Tax Forwarding Surcharge', DUTY_TAX_FORWARDING_FEE)
    if (address_correction) {
        const raw = ADDRESS_CORRECTION_PER_PKG_FEE * Math.max(1, packageCount)
        addFee('Address Correction', Math.min(raw, ADDRESS_CORRECTION_MAX_PER_SHIPMENT_FEE))
    }
    if (bill_receiver_refusal) addFee('Bill Receiver/Freight Collect Refusal Fee', BILL_RECEIVER_REFUSAL_FEE)
    if (lookup_surcharge) addFee('Look-up Surcharge', LOOKUP_SURCHARGE_FEE)
    if (rebill_fee) addFee('Rebill Fee', REBILL_FEE)
    if (document_fee) addFee('Document Fee', DOCUMENT_FEE)
    if (post_entry_clearance) addFee('Post Entry Clearance', POST_ENTRY_CLEARANCE_FEE)
    if (temporary_import_export_clearance) addFee('Temporary Import/Export Clearance', TEMP_IMPORT_EXPORT_CLEARANCE_FEE)
    if (alternate_broker) addFee('Alternate Broker', ALTERNATE_BROKER_FEE)

    if (disbursement_fee) {
        const pctAmount = duty_tax_amount > 0 ? duty_tax_amount * (DISBURSEMENT_FEE_PCT / 100) : 0
        addFee('Disbursement Fee', Math.max(DISBURSEMENT_FEE_MIN, pctAmount))
        if (duty_tax_amount <= 0) {
            notes.push('Disbursement Fee dihitung pakai nilai minimum (IDR94.159) karena nominal duty/tax belum diisi -- isi "Nilai Duty/Tax" kalau mau hitung 5.9% dari nilai sebenarnya.')
        }
    }

    // --- Signature (mutually exclusive) ---
    if (delivery_confirmation_signature && delivery_confirmation_adult_signature) {
        notes.push('Delivery Confirmation Signature Required & Adult Signature Required sama-sama ditandai -- keduanya dijumlah sesuai pilihan user, meski normalnya pengirim cuma pilih salah satu.')
    }
    if (delivery_confirmation_signature) addFee('Delivery Confirmation Signature Required', DELIVERY_CONFIRMATION_SIGNATURE_FEE)
    if (delivery_confirmation_adult_signature) addFee('Delivery Confirmation Adult Signature Required', DELIVERY_CONFIRMATION_ADULT_SIGNATURE_FEE)

    // --- UPS Import Control (mutually exclusive) ---
    if (import_control_print_label) addFee('UPS Import Control - Print Label', IMPORT_CONTROL_PRINT_LABEL_FEE)
    if (import_control_electronic_label) addFee('UPS Import Control - Electronic Label', IMPORT_CONTROL_ELECTRONIC_LABEL_FEE)

    // --- Sustainability / special cargo ---
    if (carbon_offset) {
        addFee('UPS Carbon Offset', isFreight
            ? CARBON_OFFSET_PER_PALLET_FREIGHT_FEE * Math.max(1, packageCount)
            : CARBON_OFFSET_PER_PACKAGE_FEE * Math.max(1, packageCount))
    }
    if (dry_ice) addFee('Dry Ice Surcharge', DRY_ICE_FEE * Math.max(1, packageCount))

    // --- Freight only ---
    if (delivery_reattempt) {
        if (!isFreight) {
            notes.push('Delivery Reattempt charge (IDR748.800) hanya berlaku utk UPS Worldwide Express Freight (WWEF) -- diabaikan karena service saat ini bukan WWEF (1 attempt gratis sudah termasuk di rate non-freight).')
        } else {
            addFee('Delivery Reattempt', DELIVERY_REATTEMPT_FREIGHT_FEE)
        }
    }

    // --- Compliance / exceptions ---
    if (prohibited_item) addFee('Prohibited Item Fee', PROHIBITED_ITEM_FEE_PER_PKG * Math.max(1, packageCount))
    if (paper_commercial_invoice) addFee('Paper Commercial Invoice Surcharge', PAPER_COMMERCIAL_INVOICE_FEE)
    if (pre_release_notification) addFee('Pre-Release Notification Surcharge', PRE_RELEASE_NOTIFICATION_FEE)

    // --- Additional Insurance ---
    // "For each shipment over IDR1.480.000, you may purchase additional
    // coverage against loss or damage at IDR32.710 for each additional
    // IDR1.480.000 or fraction thereof." -> nilai barang s/d threshold
    // dianggap sudah ter-cover standar (gratis), kelebihannya dikenakan
    // per kelipatan (dibulatkan ke atas).
    if (declared_value_idr > ADDITIONAL_INSURANCE_THRESHOLD_IDR) {
        const excess = declared_value_idr - ADDITIONAL_INSURANCE_THRESHOLD_IDR
        const increments = Math.ceil(excess / ADDITIONAL_INSURANCE_THRESHOLD_IDR)
        addFee('Additional Insurance', increments * ADDITIONAL_INSURANCE_PER_INCREMENT_FEE)
    } else if (declared_value_idr > 0) {
        notes.push(`Nilai barang (IDR${declared_value_idr.toLocaleString('id-ID')}) belum melebihi ambang batas Additional Insurance UPS (IDR${ADDITIONAL_INSURANCE_THRESHOLD_IDR.toLocaleString('id-ID')}) -- tidak ada surcharge tambahan.`)
    }

    const total = components.reduce((sum, c) => sum + c.amount, 0)
    return { components, total_charge: total, notes }
}

export default { computeOptionalUpsSurcharges }
