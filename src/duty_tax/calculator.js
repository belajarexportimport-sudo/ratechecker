/**
 * Kalkulator Bea Masuk & Pajak Impor Indonesia (Duty & Tax)
 * ===========================================================
 * SUMBER: di-porting PERSIS dari `calculator-ups/script.js`, fungsi
 * `calculateDutyTax()` & `checkExceptionGoods()` -- proyek kalkulator UPS
 * lain milik user sendiri (dilampirkan via calculator-ups.zip). Rumus,
 * threshold, dan rate DIPERTAHANKAN SAMA PERSIS; ini port logika yang
 * sudah dipakai user, bukan re-derivasi dari peraturan dari nol.
 *
 * KHUSUS IMPOR SAJA -- bea masuk/PPN/PPh impor cuma dikenakan saat barang
 * MASUK ke Indonesia, tidak relevan utk shipment ekspor.
 *
 * "Rumus UPS" yang dimaksud user = skema Handling Fee (2,5% / min
 * IDR200.000) & Disbursement Fee (5,9% / min IDR94.159) yang dipakai di
 * proyek UPS calculator milik user (fungsi calculateDutyTax(), baris
 * "6. Handling Fees"). FedEx punya skema surcharge sendiri utk hal serupa
 * ("Duty and Tax" ancillary clearance service, lihat fedex PDF hal.3) yang
 * BEDA & BELUM diporting -- menyusul kalau user share detailnya.
 *
 * TIDAK termasuk dalam port ini (di luar scope):
 * - HS Code autocomplete/database (hs_data.js, ~836KB) -- form ini pakai
 *   input manual (kode HS + rate BM% awal), persis seperti kalau user isi
 *   manual di app referensi tanpa pilih dari dropdown pencarian.
 * - Override rate PMK 4/2025 (per prefix HS code) TETAP diporting (lihat
 *   MFN_OVERRIDE_RULES) karena itu bagian dari RUMUS perhitungan, bukan
 *   sekadar bantuan pencarian di UI.
 */

// --- Tier thresholds (dari total FOB dalam USD, BUKAN CIF) ---
export const DEMINIMIS_MAX_FOB_USD = 3
export const FLAT_MAX_FOB_USD = 1500

// --- Rates ---
export const FLAT_BM_RATE = 0.075      // 7.5%
export const PPN_RATE = 0.11           // 11%
export const PPH_RATE_API = 0.025      // 2.5% -- importir ber-API
export const PPH_RATE_NPWP = 0.075     // 7.5% -- importir ber-NPWP (tanpa API)
export const PPH_RATE_NO_NPWP = 0.15   // 15% -- tanpa NPWP

// --- Handling (skema "UPS" sesuai kalkulator referensi user) ---
export const HANDLING_FEE_MIN = 200000
export const HANDLING_FEE_PCT = 0.025
export const DISBURSEMENT_FEE_MIN = 94159
export const DISBURSEMENT_FEE_PCT = 0.059
export const STORAGE_FEE_PER_KG_PER_DAY = 3016
export const STORAGE_FEE_MIN_DAYS = 3
export const DEFAULT_DOC_FEE_IDR = 50000

// --- PMK 4/2025: HS code prefix -> BM rate DI-OVERRIDE (menggantikan
// input rate manual user, sesuai app referensi) ---
export const MFN_OVERRIDE_RULES = [
    { prefixes: ['49'], rate: 0, label: 'Buku' },
    { prefixes: ['91'], rate: 15, label: 'Jam Tangan' },
    { prefixes: ['33'], rate: 15, label: 'Kosmetik' },
    { prefixes: ['73'], rate: 15, label: 'Besi Baja' },
    { prefixes: ['61', '62', '63'], rate: 25, label: 'Tekstil' },
    { prefixes: ['64'], rate: 25, label: 'Sepatu' },
    { prefixes: ['4202'], rate: 25, label: 'Tas' },
    { prefixes: ['8711', '8712'], rate: 25, label: 'Sepeda' },
]

// --- PMK 96/2023: HS code prefix yg WAJIB skema MFN (bukan
// deminimis/flat) apapun nilai FOB-nya ("exception/lartas goods") ---
export const MFN_EXCEPTION_PREFIXES = [
    '3303', '3304', '3305', '3306', '3307', '4202',
    '4901', '4902', '4903', '4904',
    '61', '62', '63', '64', '73', '8711', '8712', '9101', '9102',
]

function applyHsOverride(hsDigits, bmRateInput) {
    if (!hsDigits) return { bmRate: bmRateInput, overridden: false, overrideLabel: null }
    for (const rule of MFN_OVERRIDE_RULES) {
        if (rule.prefixes.some(p => hsDigits.startsWith(p))) {
            return { bmRate: rule.rate, overridden: true, overrideLabel: rule.label }
        }
    }
    return { bmRate: bmRateInput, overridden: false, overrideLabel: null }
}

function isExceptionGoods(rows) {
    return rows.some(r => r.hs_digits && MFN_EXCEPTION_PREFIXES.some(p => r.hs_digits.startsWith(p)))
}

function pphRateFor(npwpStatus) {
    if (npwpStatus === 'api') return PPH_RATE_API
    if (npwpStatus === 'no') return PPH_RATE_NO_NPWP
    return PPH_RATE_NPWP // 'yes' / default
}

/**
 * @param {Array<{hs_code?:string, bm_rate_pct?:number, value:number, currency:'USD'|'IDR'}>} items
 *   Baris barang. `bm_rate_pct` = rate Bea Masuk (%) yang diinput user utk
 *   item ini (dipakai kalau HS code tidak kena override PMK 4/2025, dan
 *   cuma relevan utk tier MFN -- diabaikan di De Minimis/Flat).
 * @param {Object} opts
 * @param {number} opts.freight_idr - ongkos kirim (IDR). App referensi
 *   pakai TOTAL AKHIR shipping (base+surcharge+FSI+VAT), bukan cuma base
 *   rate -- disarankan konsisten pakai itu.
 * @param {number} [opts.insurance_usd=0]
 * @param {number} [opts.kurs_idr=16500] - kurs pajak (Kemenkeu), dipakai
 *   konversi nilai barang/insurance dari USD ke IDR.
 * @param {'api'|'yes'|'no'} [opts.npwp_status='yes']
 * @param {Object} [opts.handling] - { enabled, doc_fee_idr, warehouse_days, weight_kg }
 * @returns {Object} breakdown lengkap, atau { error } kalau input tidak valid.
 */
export function computeDutyTax(items, opts = {}) {
    const {
        freight_idr = 0,
        insurance_usd = 0,
        kurs_idr = 16500,
        npwp_status = 'yes',
        handling = {},
    } = opts

    const notes = []
    const rows = (Array.isArray(items) ? items : [])
        .filter(it => (it.value || 0) > 0)
        .map(it => ({
            ...it,
            hs_digits: (it.hs_code || '').replace(/\D/g, ''),
            fob_idr: it.currency === 'USD' ? (it.value * kurs_idr) : it.value,
        }))

    if (rows.length === 0) {
        return { error: 'Minimal 1 item dengan nilai barang (FOB) > 0.' }
    }

    const insuranceIdr = insurance_usd * kurs_idr
    const totalGoodsFobIdr = rows.reduce((s, r) => s + r.fob_idr, 0)
    const totalSharedCost = freight_idr + insuranceIdr   // diprorata ke tiap item (share dari FOB)
    const totalCifIdr = totalGoodsFobIdr + totalSharedCost
    const totalFobUsd = kurs_idr > 0 ? totalGoodsFobIdr / kurs_idr : 0

    // 1. Tentukan tier (prioritas ketat: exception > de minimis > flat > mfn)
    const exception = isExceptionGoods(rows)
    let tier
    if (exception) tier = 'mfn-exception'
    else if (totalFobUsd <= DEMINIMIS_MAX_FOB_USD) tier = 'deminimis'
    else if (totalFobUsd <= FLAT_MAX_FOB_USD) tier = 'flat'
    else tier = 'mfn'

    let appliedBM = 0, appliedPPN = 0, appliedPPH = 0, taxBase = 0
    const itemBreakdown = []

    if (tier === 'deminimis') {
        appliedBM = 0
        taxBase = totalCifIdr
        appliedPPN = Math.round(taxBase * PPN_RATE)
        appliedPPH = 0
        notes.push(`De Minimis: total FOB USD${totalFobUsd.toFixed(2)} <= USD${DEMINIMIS_MAX_FOB_USD} -> Bea Masuk 0%, PPh 0%, PPN 11% dari CIF.`)
    } else if (tier === 'flat') {
        appliedBM = Math.round(totalCifIdr * FLAT_BM_RATE)
        taxBase = totalCifIdr + appliedBM
        appliedPPN = Math.round(taxBase * PPN_RATE)
        appliedPPH = 0
        notes.push(`Flat Rate: total FOB USD${totalFobUsd.toFixed(2)} <= USD${FLAT_MAX_FOB_USD} -> Bea Masuk flat 7.5%, PPh 0%, PPN 11%.`)
    } else {
        // mfn / mfn-exception -- Bea Masuk dihitung PER ITEM (proporsional
        // thd freight+insurance sesuai share FOB masing2 item), lalu
        // dibulatkan ke atas per IDR1.000 per item (aturan CEISA/PMK 190-2022).
        rows.forEach(r => {
            const override = applyHsOverride(r.hs_digits, r.bm_rate_pct || 0)
            const bmRate = override.bmRate
            const share = totalGoodsFobIdr > 0 ? r.fob_idr / totalGoodsFobIdr : 0
            const itemCif = r.fob_idr + (totalSharedCost * share)
            const rawDuty = itemCif * (bmRate / 100)
            const itemDuty = Math.ceil(rawDuty / 1000) * 1000
            appliedBM += itemDuty
            itemBreakdown.push({
                hs_code: r.hs_code || null,
                bm_rate_pct: bmRate,
                bm_overridden: override.overridden,
                bm_override_label: override.overrideLabel,
                item_cif_idr: Math.round(itemCif),
                item_duty_idr: itemDuty,
            })
            if (override.overridden) {
                notes.push(`HS ${r.hs_code || '(kosong)'}: rate BM di-OVERRIDE jadi ${bmRate}% (${override.overrideLabel}, ketentuan PMK 4/2025) -- bukan rate yang diinput manual.`)
            }
        })
        taxBase = totalCifIdr + appliedBM
        appliedPPN = Math.floor(taxBase * PPN_RATE)
        const pphRate = pphRateFor(npwp_status)
        appliedPPH = Math.floor(taxBase * pphRate)
        notes.push(
            (tier === 'mfn-exception'
                ? 'MFN (Exception Goods/Lartas, PMK 96/2023)'
                : `MFN (total FOB > USD${FLAT_MAX_FOB_USD})`) +
            `: Bea Masuk dihitung per item, PPh ${(pphRate * 100).toFixed(1)}% dari CIF+BM.`
        )
    }

    const totalTaxNoHandling = appliedBM + appliedPPN + appliedPPH

    // --- Handling (skema "UPS": Handling Fee + Disbursement Fee + Doc Fee + Storage Fee) ---
    let handlingBreakdown = null
    let totalHandling = 0
    if (totalTaxNoHandling > 0) {
        const suggestedHandlingFee = Math.max(HANDLING_FEE_MIN, Math.ceil(totalTaxNoHandling * HANDLING_FEE_PCT))
        const suggestedDisbursementFee = Math.max(DISBURSEMENT_FEE_MIN, Math.ceil(totalTaxNoHandling * DISBURSEMENT_FEE_PCT))

        if (handling.enabled) {
            const docFee = handling.doc_fee_idr != null ? handling.doc_fee_idr : DEFAULT_DOC_FEE_IDR
            const whDays = handling.warehouse_days || 0
            const weightKg = handling.weight_kg || 0
            const storageFee = whDays >= STORAGE_FEE_MIN_DAYS
                ? Math.ceil(STORAGE_FEE_PER_KG_PER_DAY * weightKg * whDays)
                : 0
            totalHandling = suggestedHandlingFee + suggestedDisbursementFee + docFee + storageFee
            handlingBreakdown = {
                enabled: true,
                handling_fee_idr: suggestedHandlingFee,
                disbursement_fee_idr: suggestedDisbursementFee,
                doc_fee_idr: docFee,
                warehouse_days: whDays,
                storage_fee_idr: storageFee,
                total_handling_idr: totalHandling,
            }
        } else {
            handlingBreakdown = {
                enabled: false,
                handling_fee_idr: suggestedHandlingFee,
                disbursement_fee_idr: suggestedDisbursementFee,
                doc_fee_idr: 0,
                warehouse_days: 0,
                storage_fee_idr: 0,
                total_handling_idr: 0,
            }
            notes.push('Handling Fee & Disbursement Fee di atas cuma SARAN (belum dimasukkan ke total) -- aktifkan "Hitung Import Handling" utk memasukkannya ke total.')
        }
    }

    const totalTax = totalTaxNoHandling + totalHandling
    const suggestedWarehouseDays = (tier === 'mfn' || tier === 'mfn-exception') ? 5 : STORAGE_FEE_MIN_DAYS

    return {
        tier,
        tier_label: {
            deminimis: `De Minimis (FOB <= USD${DEMINIMIS_MAX_FOB_USD})`,
            flat: `Flat Rate (FOB <= USD${FLAT_MAX_FOB_USD})`,
            mfn: `MFN (FOB > USD${FLAT_MAX_FOB_USD})`,
            'mfn-exception': 'MFN (Exception Goods/Lartas - PMK 96/2023)',
        }[tier],
        total_goods_fob_idr: Math.round(totalGoodsFobIdr),
        total_fob_usd: Math.round(totalFobUsd * 100) / 100,
        freight_idr: Math.round(freight_idr),
        insurance_idr: Math.round(insuranceIdr),
        cif_idr: Math.round(totalCifIdr),
        bea_masuk_idr: Math.round(appliedBM),
        ppn_idr: Math.round(appliedPPN),
        pph_idr: Math.round(appliedPPH),
        total_tax_no_handling_idr: Math.round(totalTaxNoHandling),
        handling: handlingBreakdown,
        total_tax_idr: Math.round(totalTax),
        suggested_warehouse_days: suggestedWarehouseDays,
        items: itemBreakdown.length > 0 ? itemBreakdown : null,
        notes,
    }
}

export default { computeDutyTax }
