/**
 * Test lengkap utk modul FedEx ancillary clearance fees (handling_fedex.js)
 * + memastikan skema UPS (handling_ups.js) tidak regresi setelah di-extract
 * dari calculator.js.
 *
 * Setiap angka di sini dihitung manual dari
 * "Clearance services and related fees FDX ID.docx" (dilampirkan user) --
 * jalankan `node test_duty_tax_fedex.js` utk verifikasi.
 */
import { computeDutyTax } from './src/duty_tax/calculator.js'
import {
    computeFedexStorageFee,
    computeProcessingFee,
    computeDisbursementFee,
    computeDutyTaxForwardingFee,
} from './src/duty_tax/handling_fedex.js'

let pass = 0
let fail = 0

function check(label, actual, expected) {
    const ok = JSON.stringify(actual) === JSON.stringify(expected)
    console.log(`${ok ? '✅' : '❌'} ${label}: actual=${JSON.stringify(actual)} | expected=${JSON.stringify(expected)}`)
    if (ok) pass++; else fail++
}

console.log('=== Unit: Processing Fee (Administration Fee) ===')
check('D&T = 100.000 (<=250k) -> gratis', computeProcessingFee(100000), 0)
check('D&T = 250.000 (batas persis) -> gratis', computeProcessingFee(250000), 0)
check('D&T = 250.001 (>250k) -> 50.000', computeProcessingFee(250001), 50000)
check('D&T = 5.000.000 -> tetap flat 50.000', computeProcessingFee(5000000), 50000)

console.log('\n=== Unit: Disbursement Fee ===')
check('D&T = 100.000 (<=250k) -> flat 60.000', computeDisbursementFee(100000), 60000)
check('D&T = 250.000 (batas persis) -> flat 60.000', computeDisbursementFee(250000), 60000)
check('D&T = 1.000.000 -> max(150000, 25000) = 150.000', computeDisbursementFee(1000000), 150000)
check('D&T = 10.000.000 (>250k, 2.5%=250rb > floor) -> 2.5%', computeDisbursementFee(10000000), 250000)

console.log('\n=== Unit: Duty and Tax Forwarding Fee (alternatif Disbursement) ===')
check('D&T = 1.000.000 -> max(290000, 25000) = 290.000', computeDutyTaxForwardingFee(1000000), 290000)
check('D&T = 20.000.000 (2.5%=500rb > 290rb floor) -> 2.5%', computeDutyTaxForwardingFee(20000000), 500000)

console.log('\n=== Unit: Storage Fee per entry type ===')
check('PIBK, 2 hari (masih dlm masa bebas) -> gratis',
    computeFedexStorageFee('pibk', 2, 10).storage_fee_idr, 0)
check('PIBK, 5 hari (2 hari billable), 10kg -> 2*(2500+2000*10)=45000',
    computeFedexStorageFee('pibk', 5, 10).storage_fee_idr, 45000)
check('BC2.3, 3 hari (persis batas bebas) -> gratis',
    computeFedexStorageFee('bc23', 3, 10).storage_fee_idr, 0)
check('BC2.3, 4 hari (1 hari billable), 5kg -> 1*(2500+2000*5)=12500',
    computeFedexStorageFee('bc23', 4, 5).storage_fee_idr, 12500)
check('PIB, 1 hari (TIDAK ada masa bebas) -> 1*(2500+2000*10)=22500',
    computeFedexStorageFee('pib', 1, 10).storage_fee_idr, 22500)
check('PIB, 0 hari -> gratis (belum nginap)',
    computeFedexStorageFee('pib', 0, 10).storage_fee_idr, 0)

console.log('\n=== Integrasi penuh: computeDutyTax(carrier="fedex") ===')

const items = [{ hs_code: '850760', bm_rate_pct: 5, value: 2000, currency: 'USD' }]

{
    // D&T = 8.182.375 (MFN tier, kurs default 16500)
    const r = computeDutyTax(items, {
        freight_idr: 500000, carrier: 'fedex',
        handling: { enabled: true, entry_type: 'pibk', warehouse_days: 5, weight_kg: 10 },
    })
    check('D&T dasar (MFN tier)', r.total_tax_no_handling_idr, 8182375)
    check('Processing Fee (D&T>250k)', r.handling.processing_fee_idr, 50000)
    check('Disbursement Fee (2.5% of D&T)', r.handling.disbursement_fee_idr, 204560)
    check('Storage Fee (PIBK, 5 hari, 10kg)', r.handling.storage.storage_fee_idr, 45000)
    check('Subtotal ancillary', r.handling.subtotal_idr, 299560)
    check('VAT ancillary (11%)', r.handling.vat_idr, 32952)
    check('Total ancillary', r.handling.total_clearance_fees_idr, 332512)
    check('Total tax akhir', r.total_tax_idr, 8514887)
}

{
    // Duty Tax Forwarding menggantikan Disbursement Fee sepenuhnya
    const r = computeDutyTax(items, {
        freight_idr: 500000, carrier: 'fedex',
        handling: {
            enabled: true, entry_type: 'pibk',
            use_duty_tax_forwarding: true,
            use_broker_document_transfer: true,
            export_formal_clearance: true,
        },
    })
    check('Disbursement Fee = 0 (digantikan)', r.handling.disbursement_fee_idr, 0)
    check('Duty Tax Forwarding Fee (floor 290rb)', r.handling.duty_tax_forwarding_fee_idr, 290000)
    check('Broker Document Transfer', r.handling.broker_document_transfer_idr, 450000)
    check('Export Formal Clearance', r.handling.export_formal_clearance_idr, 90000)
}

{
    // enabled=false -> semua fee cuma SARAN, tidak masuk total
    const r = computeDutyTax(items, {
        freight_idr: 500000, carrier: 'fedex',
        handling: { enabled: false, entry_type: 'pibk' },
    })
    check('enabled=false -> total_clearance_fees=0', r.handling.total_clearance_fees_idr, 0)
    check('enabled=false -> total_tax_idr = D&T saja', r.total_tax_idr, r.total_tax_no_handling_idr)
}

console.log('\n=== Regresi: skema UPS (setelah di-extract ke handling_ups.js) ===')
{
    const r = computeDutyTax(items, {
        freight_idr: 500000, carrier: 'ups',
        handling: { enabled: true, warehouse_days: 5, weight_kg: 10 },
    })
    check('UPS Handling Fee (2.5%, min 200rb)', r.handling.handling_fee_idr, 204560)
    check('UPS Disbursement Fee (5.9%, min 94.159)', r.handling.disbursement_fee_idr, 482761)
    check('UPS Storage Fee (3016/kg/hari x 10kg x 5hari)', r.handling.storage_fee_idr, 150800)
    check('UPS Doc Fee default', r.handling.doc_fee_idr, 50000)
}
{
    // default carrier (tidak diisi) -> harus tetap UPS (backward compat)
    const r = computeDutyTax(items, { freight_idr: 500000, handling: { enabled: false } })
    check('default carrier (tidak diisi) -> ups', r.carrier, 'ups')
}

console.log(`\n${pass} passed, ${fail} failed`)
if (fail > 0) process.exit(1)
