import { execSync } from 'child_process'
import {
    checkPackageSurcharge,
    checkFreightSurcharge,
    computeShipmentChargeableWeight,
    computeFreightChargeableWeight
} from './src/carriers/fedex/surcharges/nonstandard.js'
import { computeSpecialHandling } from './src/carriers/fedex/surcharges/special_handling.js'

let pass = 0
let fail = 0

function runPython(pyCode) {
    const cmd = `python -c "${pyCode.replace(/"/g, '\\"')}"`
    const out = execSync(cmd, { cwd: 'D:/gemini', encoding: 'utf-8' })
    return JSON.parse(out.trim())
}

function check(label, actual, expected) {
    const ok = actual === expected
    console.log(`${ok ? '✅' : '❌'} ${label}: JS=${actual} | PY=${expected}`)
    if (ok) pass++; else fail++
}

console.log('=== TEST 1: Package Surcharges (nonstandard.py) ===')

const pkgCases = [
    { label: 'Normal package 30x20x10cm 5kg', dims: [30, 20, 10], weight: 5, opts: {} },
    { label: 'AHS-Dimension (L=130cm)', dims: [130, 20, 20], weight: 5, opts: {} },
    { label: 'AHS-Weight (26kg)', dims: [30, 20, 10], weight: 26, opts: {} },
    { label: 'AHS-Packaging (non_cardboard)', dims: [30, 20, 10], weight: 5, opts: { non_cardboard_packaging: true } },
    { label: 'Oversize (L=250cm)', dims: [250, 20, 20], weight: 30, opts: {} },
    { label: 'Unauthorized Package (L=280cm)', dims: [280, 20, 20], weight: 30, opts: {} },
    { label: 'Multiple candidates (Oversize vs AHS -> highest)', dims: [250, 80, 20], weight: 30, opts: {} }
]

for (const tc of pkgCases) {
    const pyOptsStr = Object.entries(tc.opts).map(([k, v]) => `${k}=${v ? 'True' : 'False'}`).join(', ')
    const kwargsArg = pyOptsStr ? `, ${pyOptsStr}` : ''
    const pyScript = `import sys, json; sys.path.insert(0, 'D:/gemini/calculator rate comparison'); from backend.carriers.fedex.surcharges.nonstandard import check_package_surcharge; res = check_package_surcharge(${tc.dims[0]}, ${tc.dims[1]}, ${tc.dims[2]}, ${tc.weight}${kwargsArg}); print(json.dumps(res))`
    const pyRes = runPython(pyScript)
    const jsRes = checkPackageSurcharge(tc.dims[0], tc.dims[1], tc.dims[2], tc.weight, tc.opts)

    check(`${tc.label} - charge`, jsRes.charge, pyRes.charge)
    check(`${tc.label} - label`, jsRes.label, pyRes.label)
}

console.log('\n=== TEST 2: Freight Unit Surcharges (nonstandard.py) ===')

const freightCases = [
    { label: 'Normal freight 100x100x100cm 100kg', length: 100, weight: 100, width: 100, height: 100, non_stackable: false },
    { label: 'AHS-Freight (L=160cm)', length: 160, weight: 100, width: 100, height: 100, non_stackable: false },
    { label: 'Non-Stackable (3.7M)', length: 100, weight: 100, width: 100, height: 100, non_stackable: true },
    { label: 'AHS + Non-Stackable (Sum)', length: 160, weight: 100, width: 100, height: 100, non_stackable: true },
    { label: 'Unauthorized Freight (L=310cm -> Highest)', length: 310, weight: 100, width: 100, height: 100, non_stackable: true }
]

for (const tc of freightCases) {
    const pyScript = `import sys, json; sys.path.insert(0, 'D:/gemini/calculator rate comparison'); from backend.carriers.fedex.surcharges.nonstandard import check_freight_surcharge; res = check_freight_surcharge(${tc.length}, ${tc.weight}, ${tc.width}, ${tc.height}, ${tc.non_stackable ? 'True' : 'False'}); print(json.dumps(res))`
    const pyRes = runPython(pyScript)
    const jsRes = checkFreightSurcharge(tc.length, tc.weight, tc.width, tc.height, tc.non_stackable)

    check(`${tc.label} - charge`, jsRes.charge, pyRes.charge)
    check(`${tc.label} - label`, jsRes.label, pyRes.label)
}

console.log('\n=== TEST 3: Special Handling Fees (special_handling.py) ===')

const shCases = [
    { label: 'Address Correction', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { address_correction: true } },
    { label: 'Third Party Consignee', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { third_party_consignee: true } },
    { label: 'Broker Select 10kg (Min Fee)', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { broker_select: true } },
    { label: 'Broker Select 20kg (Per Kg Fee)', service: 'IP', dir: 'export', country: 'Singapore', weight: 20, opts: { broker_select: true } },
    { label: 'Saturday Pickup & Delivery', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { saturday_pickup: true, saturday_delivery: true } },
    { label: 'Inbound Processing Fee (US Export)', service: 'IP', dir: 'export', country: 'United States', weight: 10, opts: {} },
    { label: 'Inbound Processing Fee (Germany Export)', service: 'IP', dir: 'export', country: 'Germany', weight: 10, opts: {} },
    { label: 'Inbound Processing Fee (Singapore Export -> None)', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: {} },
    { label: 'ISR / DSR / ASR Non-Freight', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { isr: true, dsr: true, asr: true } },
    { label: 'ISR / DSR / ASR Freight (Ignored)', service: 'IPF', dir: 'export', country: 'Singapore', weight: 70, opts: { isr: true, dsr: true, asr: true } },
    { label: 'Residential Non-Freight US', service: 'IP', dir: 'export', country: 'United States', weight: 10, opts: { residential: true } },
    { label: 'Residential Freight Canada', service: 'IPF', dir: 'export', country: 'Canada', weight: 70, opts: { residential: true } },
    { label: 'Residential US + ODA (Mutually Exclusive)', service: 'IP', dir: 'export', country: 'United States', weight: 10, opts: { residential: true, oda_applied: true } },
    { label: 'Accessible Dangerous Goods 10kg (Min Fee)', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { accessible_dangerous_goods: true } },
    { label: 'Accessible Dangerous Goods 100kg (Per Kg Fee)', service: 'IPF', dir: 'export', country: 'Singapore', weight: 100, opts: { accessible_dangerous_goods: true } },
    { label: 'Inaccessible Dangerous Goods 10kg (Min Fee)', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { inaccessible_dangerous_goods: true } },
    { label: 'Dry Ice (Standalone)', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { dry_ice: true } },
    { label: 'Dry Ice + DG (Dry Ice Ignored)', service: 'IP', dir: 'export', country: 'Singapore', weight: 10, opts: { dry_ice: true, accessible_dangerous_goods: true } }
]

for (const tc of shCases) {
    const pyOpts = {}
    Object.keys(tc.opts).forEach(k => {
        if (typeof tc.opts[k] === 'boolean') pyOpts[k] = tc.opts[k] ? 'True' : 'False'
        else pyOpts[k] = JSON.stringify(tc.opts[k])
    })
    const pyOptsStr = Object.entries(pyOpts).map(([k, v]) => `${k}=${v}`).join(', ')
    const pyScript = `import sys, json; sys.path.insert(0, 'D:/gemini/calculator rate comparison'); from backend.carriers.fedex.surcharges.special_handling import compute_special_handling; res = compute_special_handling('${tc.service}', '${tc.dir}', '${tc.country}', ${tc.weight}, ${pyOptsStr}); print(json.dumps(res))`

    const pyRes = runPython(pyScript)
    const jsRes = computeSpecialHandling(tc.service, tc.dir, tc.country, tc.weight, tc.opts)

    check(`${tc.label} - total_charge`, jsRes.total_charge, pyRes.total_charge)
    check(`${tc.label} - components length`, jsRes.components.length, pyRes.components.length)
}

console.log(`\n========================================`)
console.log(`HASIL: ${pass} LULUS | ${fail} GAGAL dari ${pass + fail} test`)
console.log(`========================================`)
