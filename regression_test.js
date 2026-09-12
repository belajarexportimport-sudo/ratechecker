// Regression tests lengkap — verifikasi semua bug audit diperbaiki
import pricingRouter from './src/pricing/router.js'
import { lookupAndCompute, computeCharge } from './src/carriers/fedex/surcharges/oda_opa_lookup.js'

let pass = 0, fail = 0

function check(label, actual, expected, tolerance = 1) {
    const diff = Math.abs(actual - expected)
    const ok = diff <= tolerance
    console.log(`${ok ? '✅' : '❌'} ${label}: JS=${actual.toLocaleString()} | PY=${expected.toLocaleString()} | Δ=${diff}`)
    if (ok) pass++; else fail++
}

function checkEq(label, actual, expected) {
    const ok = actual === expected
    console.log(`${ok ? '✅' : '❌'} ${label}: ${actual} (expected: ${expected})`)
    if (ok) pass++; else fail++
}

function calc(opts) {
    return pricingRouter.calculate({
        carrier: opts.carrier,
        rate_type: opts.rate_type,
        service: opts.service,
        direction: opts.direction || 'export',
        origin_country: opts.origin || 'Indonesia',
        destination_country: opts.dest || 'Singapore',
        weight_kg: opts.weight,
        dimensions_cm: opts.dims || null,
        postal_code_origin: opts.postal_origin || null,
        postal_code_destination: opts.postal_dest || null,
        extra: { fsi_pct: opts.fsi ?? 14.5, ...(opts.extra || {}) },
        discount_pct: opts.disc ?? 0
    })
}

// ─── BUG #1: UPS Named-Group ───────────────────────────────────────
console.log('\n=== BUG #1: UPS A26/B26 Named-Group ===')
check('Japan A26 2kg — base_price',
    calc({ carrier:'ups', rate_type:'a26', service:'saver', dest:'Japan', weight:2 }).base_price,
    629400)
check('HK A26 5kg — base_price',
    calc({ carrier:'ups', rate_type:'a26', service:'saver', dest:'Hong Kong', weight:5 }).base_price,
    750400)
check('Thailand B26 10kg — base_price',
    calc({ carrier:'ups', rate_type:'b26', service:'saver', dest:'Thailand', weight:10 }).base_price,
    859300)

// ─── BUG #2: ODA/OPA ──────────────────────────────────────────────
console.log('\n=== BUG #2: ODA/OPA Surcharge ===')

// Jakarta 14510 Tier B = OPA max(339000, 6000*10) = 339000
const opa_b = lookupAndCompute('opa', 'parcel', 'Indonesia', '14510', null, 10)
checkEq('Jakarta 14510 → Tier B', opa_b.tier, 'B')
check('OPA Tier B 10kg charge', opa_b.charge, 339000)

// Papua 98418 Tier C = max(442000, 8000*10) = 442000
const opa_c = lookupAndCompute('opa', 'parcel', 'Indonesia', '98418', null, 10)
checkEq('Papua 98418 → Tier C', opa_c.tier, 'C')
check('OPA Tier C 10kg charge', opa_c.charge, 442000)

// ODA Tier A = flat 52000, no per-kg
check('ODA Tier A 5kg charge', computeCharge('oda', 'A', 5), 52000)
// ODA Tier B = max(339000, 6000*60) = 360000
check('ODA Tier B 60kg charge', computeCharge('oda', 'B', 60), 360000)

// Calculator integration: FedEx ekspor ke SG + OPA Jakarta
const fdx_opa = calc({
    carrier:'fedex', rate_type:'publish', service:'IP',
    dest:'Singapore', weight:10, postal_origin:'14510', fsi:0
})
check('FedEx SG 10kg + OPA Jakarta (no FSI) surcharge sum',
    Object.values(fdx_opa.surcharges).reduce((a,b)=>a+b, 0),
    339000)

// ─── BUG #3: Demand Surcharge (tanggal efektif belum tiba) ───────
console.log('\n=== BUG #3: Demand Surcharge belum berlaku ===')
const fdx_jp = calc({ carrier:'fedex', rate_type:'publish', service:'IP', dest:'Japan', weight:5, fsi:0 })
checkEq('Demand Surcharge tidak ada di surcharges',
    'Demand Surcharge' in fdx_jp.surcharges, false)
check('FedEx Japan 5kg no-FSI total = Python verified',
    fdx_jp.total, 4411000)

// ─── BUG #5: IPF/IEF minimum 68kg ────────────────────────────────
console.log('\n=== BUG #5: FedEx IPF Minimum 68kg ===')
const ipf_10 = calc({ carrier:'fedex', rate_type:'publish', service:'IPF', dest:'Singapore', weight:10, fsi:0 })
check('IPF 10kg actual → chargeable 68kg', ipf_10.extra.chargeable_weight, 68)

// ─── pyRound ─────────────────────────────────────────────────────
console.log('\n=== pyRound: UPS Publish SG 2kg FSI 15% ===')
check('UPS SG 2kg FSI 15% total',
    calc({ carrier:'ups', rate_type:'publish', service:'saver', dest:'Singapore', weight:2, fsi:15 }).total,
    2083451)

// ─── BUG #6: Auto-switch IP/IE -> IPF/IEF tidak jalan lewat dimensions_cm ─
// Ditemukan dari laporan user: input dims 52x50x90cm (length+girth=332cm
// >330cm) via UI (yang kirim dimensions_cm, BUKAN packages[]) -> service
// harusnya WAJIB pindah ke IPF, tapi tetap "IP". Root cause: wiring
// auto-switch di calculator.js cuma cek request.packages, padahal
// public/index.html (frontend yang benar-benar dipakai) selalu kirim
// dimensions_cm untuk kasus 1 collie. Fix: dimensions_cm sekarang
// di-treat sbg 1 package implisit utk switch-check juga.
console.log('\n=== BUG #6: Auto-switch via dimensions_cm (single box) ===')
const switchCase = calc({ carrier:'fedex', rate_type:'publish', service:'IP',
    dest:'Singapore', weight:10, dims:[52,50,90], fsi:0 })
checkEq('Dims 52x50x90cm (girth+length=332cm>330) -> auto-switch service ke IPF',
    switchCase.service, 'IPF')
checkEq('Setelah switch ke IPF, Oversize Charge (khusus IP/IE) tidak lagi dikenakan',
    'Oversize Charge' in switchCase.surcharges, false)

// Kontrol negatif: box yang MASIH dalam batas IP tidak boleh ke-switch.
const noSwitchCase = calc({ carrier:'fedex', rate_type:'publish', service:'IP',
    dest:'Singapore', weight:10, dims:[40,30,30], fsi:0 })
checkEq('Dims 40x30x30cm (dalam batas) -> service TETAP IP (kontrol negatif)',
    noSwitchCase.service, 'IP')

// ─── BUG #7: UPS tidak dukung packages[] (multi-collie) -- cuma dimensions_cm ─
// Ditemukan saat nambah fitur "collie 2, 3, dst" di UI: FedEx sudah dukung
// request.packages[] sejak BUG #6, tapi UPS calculator.js CUMA baca
// request.dimensions_cm (single box) -- utk shipment >1 collie, UPS diam-diam
// kehilangan dim-weight & surcharge AHS/LPS/OMX per-collie (cuma pakai
// weight_kg total tanpa dimensi sama sekali). Fix: UPS sekarang loop per
// collie, sama seperti FedEx.
console.log('\n=== BUG #7: UPS multi-collie (packages[]) ===')
const upsMulti = pricingRouter.calculate({
    carrier: 'ups', rate_type: 'publish', service: 'saver', direction: 'export',
    origin_country: 'Indonesia', destination_country: 'Singapore', weight_kg: 15,
    packages: [
        { label: 'Collie 1', length_cm: 30, width_cm: 30, height_cm: 30, weight_kg: 5 },
        { label: 'Collie 2', length_cm: 140, width_cm: 60, height_cm: 60, weight_kg: 10 },
    ],
    extra: { fsi_pct: 0 },
})
check('2 collie -> chargeable weight = jumlah dim/actual weight per collie (5.4+100.8)',
    upsMulti.extra.chargeable_weight, 106.2, 0.01)
checkEq('Collie 2 (length+girth=380cm>300) -> LPS ke-trigger dgn label collie-nya',
    'Large Package Surcharge (LPS) (Collie 2)' in upsMulti.surcharges, true)
checkEq('Collie 1 (dalam batas) -> TIDAK kena surcharge apapun',
    Object.keys(upsMulti.surcharges).some(k => k.includes('Collie 1')), false)

// Kontrol: mode single-package (dimensions_cm) HARUS tetap jalan spt sebelumnya
// (fix packages[] tidak boleh mengubah jalur lama).
const upsSingle = pricingRouter.calculate({
    carrier: 'ups', rate_type: 'publish', service: 'saver', direction: 'export',
    origin_country: 'Indonesia', destination_country: 'Singapore', weight_kg: 2,
    dimensions_cm: [30, 20, 15], extra: { fsi_pct: 15 },
})
check('Mode single dimensions_cm (bukan packages[]) tidak berubah (kontrol negatif)',
    upsSingle.total, 2083451)

// ─── BUG #8: Kondisi kemasan (AHS-Packaging) harus PER-COLLIE, bukan global ─
// Ditemukan dari pertanyaan user: "gimana kalau collie 1 silinder, collie 2
// box normal?" -- sebelum fix ini, form cuma punya 1 set checkbox kemasan
// yang diterapkan sama ke SEMUA collie (tidak bisa beda per collie).
console.log('\n=== BUG #8: Kondisi kemasan per-collie (bukan global) ===')
const mixedPkgFedex = pricingRouter.calculate({
    carrier: 'fedex', rate_type: 'publish', service: 'IP', direction: 'export',
    origin_country: 'Indonesia', destination_country: 'Singapore', weight_kg: 10,
    packages: [
        { label: 'Collie 1', length_cm: 30, width_cm: 30, height_cm: 30, weight_kg: 5, round_or_cylindrical: true },
        { label: 'Collie 2', length_cm: 40, width_cm: 30, height_cm: 20, weight_kg: 5 },
    ],
    extra: {},
})
checkEq('Collie 1 (silinder) -> kena AHS-Packaging',
    'AHS - Packaging (Collie 1)' in mixedPkgFedex.surcharges, true)
checkEq('Collie 2 (box biasa, TANPA flag) -> TIDAK ikut kena AHS-Packaging',
    Object.keys(mixedPkgFedex.surcharges).some(k => k.startsWith('AHS - Packaging') && k.includes('Collie 2')), false)

// ─── Summary ─────────────────────────────────────────────────────
console.log(`\n${'═'.repeat(40)}`)
console.log(`HASIL: ${pass} LULUS | ${fail} GAGAL dari ${pass+fail} test`)
console.log('═'.repeat(40))
