/**
 * UPS Layanan Tambahan / Surcharge Opsional (manual tick)
 * ========================================================
 * Sumber: "2026 UPS Rate and Service Guide Indonesia" (effective 7 Jun 2026),
 * halaman 4-8 ("Services with Additional Charges" & "Other Additional
 * Charges"). Semua nominal di bawah dikutip PERSIS dari PDF itu -- bukan
 * estimasi.
 *
 * UPDATE: Extended Area (EAS) & Remote Area (RAS) SEKARANG OTOMATIS
 * berdasarkan kode pos/kota, pakai data resmi UPS "ea-surcharge-en-GLOBAL
 * efektif 7 Juni 2026.xlsx" (lihat eas_ras_data.js & eas_ras_lookup.js,
 * hasil ekstrak dari calculator-ups.zip yang user lampirkan -- proyek
 * kalkulator UPS lain milik user sendiri yang sudah lebih dulu
 * mem-parsing xlsx ini). Checkbox manual TETAP ada sbg fallback utk
 * negara yang tidak tercakup data (data cuma tercakup ~86 negara --
 * lihat komentar di eas_ras_data.js).
 *
 * Pola & penamaan field disamakan dgn special_handling.js FedEx supaya
 * caller (calculator.js) konsisten, TAPI ini modul terpisah -- kriteria
 * & nominal UPS beda dari FedEx, tidak dipaksa disatukan.
 *
 * BELUM dimasukkan (sengaja, di luar scope "tinggal tick" / bukan opsi yang
 * dipilih shipper sebelum kirim, atau perlu field lain yang belum ada di
 * schema, mis. declared value):
 * - Additional Insurance (butuh input nilai barang/declared value)
 * - Undeliverable Package Return Charge, Bill Receiver/Freight Collect
 *   Refusal Fee, Look-up Surcharge, Rebill Fee, Prohibited Item Fee,
 *   Unlawful Drug Fee, Return to Shipper (semua fee EXCEPTION/pasca-kejadian,
 *   bukan pilihan preventif shipper)
 * - UPS Returns (Print/Electronic/Return Label, Returns Plus) -- beda alur
 *   (bukan outbound shipment biasa)
 * - UPS Import Control, Commercial Invoice Removal -- perlu smart-label
 *   compliant system, di luar scope kalkulator rate
 * - Disbursement Fee, Warehouse Storage, Document Fee, Post Entry Clearance,
 *   Temporary Import/Export Clearance -- proses customs pasca-shipment,
 *   bukan pilihan di titik kalkulasi rate
 */
import { lookupEasRas } from './eas_ras_lookup.js'


export const SATURDAY_DELIVERY_NON_FREIGHT_FEE = 171680
export const SATURDAY_DELIVERY_FREIGHT_FEE = 3432120  // UPS Worldwide Express Freight Services

export const DIRECT_DELIVERY_ONLY_FEE = 31080  // per package

export const RESIDENTIAL_NON_FREIGHT_FEE = 58312
export const RESIDENTIAL_FREIGHT_FEE = 1879600  // UPS Worldwide Express Freight Services

export const EXTENDED_AREA_MIN_FEE = 429792
export const EXTENDED_AREA_PER_KG = 8288

export const REMOTE_AREA_MIN_FEE = 479964
export const REMOTE_AREA_PER_KG = 9472

export const EXPORT_DECLARATION_FEE = 190189   // "PEB" -- Pemberitahuan Ekspor Barang
export const IMPORT_DECLARATION_FEE = 190977

export const DELIVERY_CONFIRMATION_SIGNATURE_FEE = 37740
export const DELIVERY_CONFIRMATION_ADULT_SIGNATURE_FEE = 71040

export const DUTY_TAX_FORWARDING_FEE = 310060  // import only

export const PAPER_COMMERCIAL_INVOICE_MAX_FEE = 370000  // "maximum charge"

export const CARBON_OFFSET_PACKAGE_FEE = 11690
export const CARBON_OFFSET_PALLET_FEE = 311980  // UPS Worldwide Express Freight Services

export const ADDRESS_CORRECTION_PER_PACKAGE_FEE = 187072
export const ADDRESS_CORRECTION_MAX_PER_SHIPMENT_FEE = 653420

/**
 * Hitung semua surcharge opsional (manual tick) UPS untuk 1 shipment.
 * `opts` -- semua boolean, default false (tidak berubah kalau tidak diisi).
 * `is_freight` -- true kalau service = wwef (dipetakan ke "UPS Worldwide
 * Express Freight Services" utk tarif Saturday Delivery/Residential/Carbon
 * Offset versi freight).
 * `package_count` -- dipakai utk Direct Delivery Only & Carbon Offsets
 * (dikenakan PER PACKAGE), default 1.
 */
export function computeOptionalSurcharges(direction, chargeable_weight_kg, opts = {}, country = '', postalCode = '') {
    const {
        is_freight = false,
        package_count = 1,
        saturday_delivery = false,
        direct_delivery_only = false,
        residential = false,
        extended_area = false,
        remote_area = false,
        export_declaration = false,   // "PEB"
        import_declaration = false,
        delivery_confirmation_signature = false,
        delivery_confirmation_adult_signature = false,
        duty_tax_forwarding = false,
        paper_commercial_invoice = false,
        carbon_offset = false,
        address_correction = false,
    } = opts

    const components = []
    const notes = []
    const isImport = direction === 'import'

    if (saturday_delivery) {
        const amount = is_freight ? SATURDAY_DELIVERY_FREIGHT_FEE : SATURDAY_DELIVERY_NON_FREIGHT_FEE
        components.push({ label: 'Saturday Delivery', amount })
    }

    if (direct_delivery_only) {
        components.push({ label: 'Direct Delivery Only', amount: DIRECT_DELIVERY_ONLY_FEE * Math.max(1, package_count) })
    }

    // Extended/Remote Area -- OTOMATIS dulu (data resmi kode pos UPS), baru
    // fallback ke checkbox manual kalau kode posnya tidak tercakup data.
    const autoType = country ? lookupEasRas(country, postalCode, '', isImport ? 'origin' : 'destination') : null

    if (autoType === 'RAS') {
        components.push({ label: 'Remote Area Surcharge', amount: Math.max(REMOTE_AREA_MIN_FEE, REMOTE_AREA_PER_KG * chargeable_weight_kg) })
        notes.push(`Remote Area Surcharge terdeteksi OTOMATIS dari kode pos ${postalCode || '(kosong)'} (${country}), bukan dari centang manual.`)
        if (extended_area) notes.push('Centang manual Extended Area diabaikan -- kode pos ini sudah terdeteksi Remote Area (lebih tinggi) dari data resmi.')
    } else if (autoType === 'EAS') {
        components.push({ label: 'Extended Area Surcharge (DAS)', amount: Math.max(EXTENDED_AREA_MIN_FEE, EXTENDED_AREA_PER_KG * chargeable_weight_kg) })
        notes.push(`Extended Area Surcharge terdeteksi OTOMATIS dari kode pos ${postalCode || '(kosong)'} (${country}), bukan dari centang manual.`)
        if (remote_area) notes.push('Centang manual Remote Area diabaikan -- kode pos ini terdeteksi Extended Area (bukan Remote) dari data resmi.')
    } else {
        // Tidak terdeteksi otomatis (negara di luar cakupan data, atau kode
        // pos memang tidak kena EAS/RAS) -- pakai checkbox manual sbg fallback.
        if (extended_area && remote_area) {
            notes.push('Extended Area & Remote Area (manual) sama-sama dicentang -- ini seharusnya saling eksklusif (1 titik lokasi cuma salah satu). Kedua surcharge tetap DIJUMLAH krn tidak ada aturan resolusi eksplisit di PDF -- cek ulang kalau ini bukan yang dimaksud.')
        }
        if (extended_area) {
            components.push({ label: 'Extended Area Surcharge (DAS)', amount: Math.max(EXTENDED_AREA_MIN_FEE, EXTENDED_AREA_PER_KG * chargeable_weight_kg) })
            notes.push('Extended Area Surcharge dari centang manual (kode pos ini tidak tercakup data resmi UPS yang dipakai kalkulator ini).')
        }
        if (remote_area) {
            components.push({ label: 'Remote Area Surcharge', amount: Math.max(REMOTE_AREA_MIN_FEE, REMOTE_AREA_PER_KG * chargeable_weight_kg) })
            notes.push('Remote Area Surcharge dari centang manual (kode pos ini tidak tercakup data resmi UPS yang dipakai kalkulator ini).')
        }
    }

    if (residential) {
        const amount = is_freight ? RESIDENTIAL_FREIGHT_FEE : RESIDENTIAL_NON_FREIGHT_FEE
        components.push({ label: 'Residential Surcharge', amount })
    }

    if (export_declaration) {
        if (!isImport) {
            components.push({ label: 'Export Declaration Surcharge (PEB)', amount: EXPORT_DECLARATION_FEE })
        } else {
            notes.push('Export Declaration Surcharge (PEB) cuma berlaku utk shipment EKSPOR -> diabaikan (arah saat ini: import).')
        }
    }
    if (import_declaration) {
        if (isImport) {
            components.push({ label: 'Import Declaration Surcharge', amount: IMPORT_DECLARATION_FEE })
        } else {
            notes.push('Import Declaration Surcharge cuma berlaku utk shipment IMPOR -> diabaikan (arah saat ini: export).')
        }
    }

    if (delivery_confirmation_adult_signature) {
        components.push({ label: 'Delivery Confirmation Adult Signature Required', amount: DELIVERY_CONFIRMATION_ADULT_SIGNATURE_FEE })
        if (delivery_confirmation_signature) {
            notes.push('Delivery Confirmation Signature Required & Adult Signature Required sama-sama dicentang -- keduanya beda layanan (bukan upgrade satu sama lain seperti FedEx ISR/DSR/ASR), jadi tetap DIJUMLAH sesuai PDF (tidak ada aturan mutually-exclusive disebutkan).')
            components.push({ label: 'Delivery Confirmation Signature Required', amount: DELIVERY_CONFIRMATION_SIGNATURE_FEE })
        }
    } else if (delivery_confirmation_signature) {
        components.push({ label: 'Delivery Confirmation Signature Required', amount: DELIVERY_CONFIRMATION_SIGNATURE_FEE })
    }

    if (duty_tax_forwarding) {
        if (isImport) {
            components.push({ label: 'Duty/Tax Forwarding Surcharge', amount: DUTY_TAX_FORWARDING_FEE })
        } else {
            notes.push('Duty/Tax Forwarding Surcharge cuma berlaku utk shipment IMPOR -> diabaikan (arah saat ini: export).')
        }
    }

    if (paper_commercial_invoice) {
        components.push({ label: 'Paper Commercial Invoice Surcharge (maks.)', amount: PAPER_COMMERCIAL_INVOICE_MAX_FEE })
    }

    if (carbon_offset) {
        const amount = is_freight ? CARBON_OFFSET_PALLET_FEE : CARBON_OFFSET_PACKAGE_FEE * Math.max(1, package_count)
        components.push({ label: 'UPS Carbon Offsets', amount })
    }

    if (address_correction) {
        const amount = Math.min(ADDRESS_CORRECTION_PER_PACKAGE_FEE * Math.max(1, package_count), ADDRESS_CORRECTION_MAX_PER_SHIPMENT_FEE)
        components.push({ label: 'Address Correction', amount })
        notes.push('Address Correction biasanya fee EXCEPTION (dikenakan FedEx/UPS setelah alamat terbukti salah), bukan pilihan yang biasa di-tick di awal -- centang cuma kalau memang mau simulasikan skenario ini.')
    }

    const total = components.reduce((sum, c) => sum + c.amount, 0)
    return { components, total_charge: total, notes }
}
