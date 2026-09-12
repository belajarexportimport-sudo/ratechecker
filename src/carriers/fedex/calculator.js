import { getZone, getZoneCommercial } from './zones.js'
import { calculateBase } from './rates/index.js'
import { pyRound } from '../../core/pyround.js'
import { lookupAndCompute } from './surcharges/oda_opa_lookup.js'
import {
    checkPackageSurcharge,
    checkFreightSurcharge,
    computeShipmentChargeableWeight,
    computeFreightChargeableWeight,
    evaluatePackagesForServiceSwitch,
} from './surcharges/nonstandard.js'
import { computeSpecialHandling } from './surcharges/special_handling.js'
import {
    calculateDimWeight,
    MINIMUM_BILLED_WEIGHT_KG,
    MINIMUM_FREIGHT_WEIGHT_KG,
    isFreight
} from './rules.js'

// =============================================================================
// PERBAIKAN KRITIS #3: Demand Surcharge per-region + tanggal efektif
// Sumber: demand_surcharge_update_4_sep_2026.pdf, efektif 21 September 2026
// =============================================================================
const DEMAND_EFFECTIVE_DATE = new Date('2026-09-21T00:00:00')
const DEMAND_MIN_PER_SHIPMENT = 4200  // IDR

// Tabel per-region (IDR per kg) — IP/IE = priority, IPF/IEF = economy
const DEMAND_TABLE = {
    export: {
        'Australia, Fiji, New Zealand':              { priority: 8400,  economy: 8400  },
        'Vietnam':                                   { priority: 0,     economy: 0     },
        'Asia':                                      { priority: 3000,  economy: 3000  },
        'United States (U.S.) and Puerto Rico':      { priority: 26800, economy: 20100 },
        'Canada':                                    { priority: 26800, economy: 20100 },
        'Mexico':                                    { priority: 26800, economy: 20100 },
        'Latin America and Caribbean (LAC)':         { priority: 26800, economy: 20100 },
        'Israel':                                    { priority: 21800, economy: 21800 },
        'Europe':                                    { priority: 21800, economy: 21800 },
        'India':                                     { priority: 1800,  economy: 1800  },
        'MEISA Group 1':                             { priority: 25600, economy: 25600 },
        'MEISA Group 2':                             { priority: 41900, economy: 41900 },
    },
    import: {
        'Australia, Fiji, New Zealand':              { priority: 3000,  economy: 3000  },
        'Vietnam':                                   { priority: 0,     economy: 0     },
        'Asia':                                      { priority: 3000,  economy: 3000  },
        'United States (U.S.) and Puerto Rico':      { priority: 0,     economy: 0     },
        'Canada':                                    { priority: 0,     economy: 0     },
        'Mexico':                                    { priority: 0,     economy: 0     },
        'Latin America and Caribbean (LAC)':         { priority: 0,     economy: 0     },
        'Israel':                                    { priority: 1700,  economy: 1700  },
        'Europe':                                    { priority: 1700,  economy: 1700  },
        'India':                                     { priority: 9200,  economy: 9200  },
        'MEISA Group 1':                             { priority: 18300, economy: 18300 },
        'MEISA Group 2':                             { priority: 18300, economy: 18300 },
    }
}

// 226 negara → region (dari demand_surcharge_update_4_sep_2026.pdf)
const DEMAND_COUNTRY_TO_REGION = {"australia":"Australia, Fiji, New Zealand","fiji":"Australia, Fiji, New Zealand","new zealand":"Australia, Fiji, New Zealand","vietnam":"Vietnam","american samoa":"Asia","brunei":"Asia","cambodia":"Asia","china":"Asia","cook islands":"Asia","east timor":"Asia","french polynesia":"Asia","guam":"Asia","hong kong":"Asia","japan":"Asia","laos":"Asia","macau":"Asia","malaysia":"Asia","marshall islands":"Asia","micronesia":"Asia","mongolia":"Asia","new caledonia":"Asia","northern mariana islands":"Asia","palau":"Asia","papua new guinea":"Asia","philippines":"Asia","rota":"Asia","saipan":"Asia","samoa":"Asia","singapore":"Asia","south korea":"Asia","tahiti":"Asia","taiwan":"Asia","thailand":"Asia","tinian":"Asia","tonga":"Asia","vanuatu":"Asia","wallis & futuna":"Asia","united states (rest of country)":"United States (U.S.) and Puerto Rico","united states (western region)":"United States (U.S.) and Puerto Rico","puerto rico":"United States (U.S.) and Puerto Rico","canada":"Canada","mexico":"Mexico","anguilla":"Latin America and Caribbean (LAC)","antigua":"Latin America and Caribbean (LAC)","argentina":"Latin America and Caribbean (LAC)","aruba":"Latin America and Caribbean (LAC)","bahamas":"Latin America and Caribbean (LAC)","barbados":"Latin America and Caribbean (LAC)","barbuda":"Latin America and Caribbean (LAC)","belize":"Latin America and Caribbean (LAC)","bermuda":"Latin America and Caribbean (LAC)","bolivia":"Latin America and Caribbean (LAC)","bonaire":"Latin America and Caribbean (LAC)","brazil":"Latin America and Caribbean (LAC)","british virgin islands":"Latin America and Caribbean (LAC)","cayman islands":"Latin America and Caribbean (LAC)","chile":"Latin America and Caribbean (LAC)","colombia":"Latin America and Caribbean (LAC)","costa rica":"Latin America and Caribbean (LAC)","curacao":"Latin America and Caribbean (LAC)","dominica":"Latin America and Caribbean (LAC)","dominican republic":"Latin America and Caribbean (LAC)","ecuador":"Latin America and Caribbean (LAC)","el salvador":"Latin America and Caribbean (LAC)","french guiana":"Latin America and Caribbean (LAC)","grand cayman":"Latin America and Caribbean (LAC)","great thatch island":"Latin America and Caribbean (LAC)","great tobago islands":"Latin America and Caribbean (LAC)","grenada":"Latin America and Caribbean (LAC)","guadeloupe":"Latin America and Caribbean (LAC)","guatemala":"Latin America and Caribbean (LAC)","guyana":"Latin America and Caribbean (LAC)","haiti":"Latin America and Caribbean (LAC)","honduras":"Latin America and Caribbean (LAC)","jamaica":"Latin America and Caribbean (LAC)","jost van dyke islands":"Latin America and Caribbean (LAC)","martinique":"Latin America and Caribbean (LAC)","montserrat":"Latin America and Caribbean (LAC)","nevis":"Latin America and Caribbean (LAC)","nicaragua":"Latin America and Caribbean (LAC)","norman island":"Latin America and Caribbean (LAC)","panama":"Latin America and Caribbean (LAC)","paraguay":"Latin America and Caribbean (LAC)","peru":"Latin America and Caribbean (LAC)","saba":"Latin America and Caribbean (LAC)","st. barthelemy":"Latin America and Caribbean (LAC)","st. christopher":"Latin America and Caribbean (LAC)","st. croix island":"Latin America and Caribbean (LAC)","st. eustatius":"Latin America and Caribbean (LAC)","st. john":"Latin America and Caribbean (LAC)","st. kitts & nevis":"Latin America and Caribbean (LAC)","st. lucia":"Latin America and Caribbean (LAC)","st. maarten":"Latin America and Caribbean (LAC)","st. martin":"Latin America and Caribbean (LAC)","st. thomas":"Latin America and Caribbean (LAC)","st. vincent":"Latin America and Caribbean (LAC)","suriname":"Latin America and Caribbean (LAC)","tortola island":"Latin America and Caribbean (LAC)","trinidad & tobago":"Latin America and Caribbean (LAC)","turks & caicos islands":"Latin America and Caribbean (LAC)","u.s. virgin islands":"Latin America and Caribbean (LAC)","union island":"Latin America and Caribbean (LAC)","uruguay":"Latin America and Caribbean (LAC)","venezuela":"Latin America and Caribbean (LAC)","israel":"Israel","albania":"Europe","andorra":"Europe","armenia":"Europe","austria":"Europe","azerbaijan":"Europe","belarus":"Europe","belgium":"Europe","bosnia-herzegovina":"Europe","bulgaria":"Europe","canary islands":"Europe","channel islands":"Europe","croatia":"Europe","cyprus":"Europe","czech republic":"Europe","denmark":"Europe","estonia":"Europe","faeroe islands":"Europe","finland":"Europe","france":"Europe","georgia":"Europe","germany":"Europe","gibraltar":"Europe","greece":"Europe","greenland":"Europe","hungary":"Europe","iceland":"Europe","ireland":"Europe","italy":"Europe","latvia":"Europe","liechtenstein":"Europe","lithuania":"Europe","luxembourg":"Europe","macedonia":"Europe","malta":"Europe","moldova":"Europe","monaco":"Europe","montenegro":"Europe","netherlands":"Europe","norway":"Europe","poland":"Europe","portugal":"Europe","romania":"Europe","russia":"Europe","san marino":"Europe","serbia":"Europe","slovak republic":"Europe","slovenia":"Europe","spain":"Europe","sweden":"Europe","switzerland":"Europe","turkey":"Europe","ukraine":"Europe","united kingdom":"Europe","vatican city":"Europe","india":"India","afghanistan":"MEISA Group 1","bahrain":"MEISA Group 1","bangladesh":"MEISA Group 1","bhutan":"MEISA Group 1","egypt":"MEISA Group 1","jordan":"MEISA Group 1","kuwait":"MEISA Group 1","kyrgyzstan":"MEISA Group 1","maldives":"MEISA Group 1","nepal":"MEISA Group 1","oman":"MEISA Group 1","palestine autonomous":"MEISA Group 1","saudi arabia":"MEISA Group 1","sri lanka":"MEISA Group 1","united arab emirates":"MEISA Group 1","uzbekistan":"MEISA Group 1","algeria":"MEISA Group 2","angola":"MEISA Group 2","benin":"MEISA Group 2","botswana":"MEISA Group 2","burkina faso":"MEISA Group 2","burundi":"MEISA Group 2","cameroon":"MEISA Group 2","cape verde":"MEISA Group 2","chad":"MEISA Group 2","congo":"MEISA Group 2","congo dem rep of":"MEISA Group 2","djibouti":"MEISA Group 2","eritrea":"MEISA Group 2","ethiopia":"MEISA Group 2","gabon":"MEISA Group 2","gambia":"MEISA Group 2","ghana":"MEISA Group 2","guinea":"MEISA Group 2","iraq":"MEISA Group 2","ivory coast":"MEISA Group 2","kazakhstan":"MEISA Group 2","kenya":"MEISA Group 2","lebanon":"MEISA Group 2","lesotho":"MEISA Group 2","liberia":"MEISA Group 2","libya":"MEISA Group 2","madagascar":"MEISA Group 2","malawi":"MEISA Group 2","mali":"MEISA Group 2","mauritania":"MEISA Group 2","mauritius":"MEISA Group 2","morocco":"MEISA Group 2","mozambique":"MEISA Group 2","namibia":"MEISA Group 2","niger":"MEISA Group 2","nigeria":"MEISA Group 2","pakistan":"MEISA Group 2","qatar":"MEISA Group 2","reunion":"MEISA Group 2","rwanda":"MEISA Group 2","senegal":"MEISA Group 2","seychelles":"MEISA Group 2","south africa":"MEISA Group 2","swaziland":"MEISA Group 2","tanzania":"MEISA Group 2","togo":"MEISA Group 2","tunisia":"MEISA Group 2","uganda":"MEISA Group 2","zambia":"MEISA Group 2","zimbabwe":"MEISA Group 2"}

function isDemandActive() {
    return new Date() >= DEMAND_EFFECTIVE_DATE
}

function computeDemandSurcharge(service, direction, country, weight) {
    if (!isDemandActive()) return 0
    const region = DEMAND_COUNTRY_TO_REGION[country.toLowerCase()]
    if (!region) return 0  // negara tidak terpetakan → tidak dikenakan
    const dirKey = direction === 'import' ? 'import' : 'export'
    const regionRates = DEMAND_TABLE[dirKey]?.[region]
    if (!regionRates) return 0
    // IP/IE = priority, IPF/IEF/lainnya = economy
    const svcUpper = service.toUpperCase()
    const ratePerKg = (svcUpper === 'IP' || svcUpper === 'IE') ? regionRates.priority : regionRates.economy
    if (!ratePerKg) return 0
    return pyRound(Math.max(ratePerKg * Math.ceil(weight), DEMAND_MIN_PER_SHIPMENT))

}

// =============================================================================
// FedEx Calculator
// =============================================================================

export function calculate(request) {
    const direction = request.direction.toLowerCase()
    let service     = request.service.toUpperCase()
    const isImport  = direction === 'import'

    const country    = isImport ? request.origin_country     : request.destination_country
    const postalCode = isImport ? request.postal_code_origin : request.postal_code_destination

    // === Resolve zone (semua service IP/IE/IPF/IEF sekaligus -- dipakai lagi
    // di bawah kalau auto-switch terjadi, tanpa perlu lookup ulang) ===
    let zone
    if (request.rate_type === 'commercial') {
        zone = getZoneCommercial(country, isImport, postalCode, null)
    } else {
        zone = getZone(country, isImport, postalCode, null)
    }

    // === PERBAIKAN: Auto-switch IP/IE -> IPF/IEF ===
    // evaluatePackagesForServiceSwitch() (nonstandard.js) SUDAH ADA sejak
    // sebelumnya tapi TIDAK PERNAH dipanggil di sini -> package yang
    // melebihi batas (mis. length+girth > 330cm) TIDAK PERNAH auto-switch
    // ke freight, service tetap IP/IE walau seharusnya wajib pindah (bug
    // ditemukan saat audit: dims 52x50x90cm -> length+girth=332cm>330cm).
    // Port persis dari backend/carriers/fedex/calculator.py Tahap 4.
    let effectiveWeightKg = request.weight_kg
    let packagesForCwt = request.packages
    const switchNotes = []
    if (!isFreight(service) && request.packages && request.packages.length > 0
        && request.auto_switch_service !== false) {
        const switchInfo = evaluatePackagesForServiceSwitch(service, request.packages)
        if (switchInfo.action === 'switch') {
            const forcedLines = switchInfo.forced_fee_preview.map(f => {
                const extra = f.forced_label
                    ? ` Kalau dipaksakan tetap ${service}, akan kena ${f.forced_label} ` +
                      `(IDR ${f.forced_charge.toLocaleString('id-ID')}/collie).`
                    : ''
                return `${f.label}: ${f.reasons.join(', ')}.${extra}`
            })
            switchNotes.push(
                `Semua collie melebihi batas maksimum ${service} -> service OTOMATIS ` +
                `dialihkan dari ${service} ke ${switchInfo.new_service}. ` + forcedLines.join(' | ')
            )
            request.freight_units = request.packages.map((p, i) => ({
                label: p.label || `Collie ${i + 1}`,
                length_cm: p.length_cm,
                width_cm: p.width_cm,
                height_cm: p.height_cm,
                weight_kg: p.weight_kg,
                non_stackable: false,
            }))
            effectiveWeightKg = request.packages.reduce((s, p) => s + p.weight_kg, 0)
            packagesForCwt = null
            service = switchInfo.new_service
        }
        // action === 'none' -> lanjut normal. action === 'switch' sudah
        // ditangani; ShipmentSplitRequired (kalau ada) dibiarkan propagate
        // ke caller, sama seperti Python (tidak diam-diam ditangani di sini).
    }
    request.weight_kg = effectiveWeightKg
    request.packages = packagesForCwt

    // zone returns {IP: 'A', IE: 'A', IPF: 'A', IEF: 'A'} — extract untuk service ini
    const zoneCode = typeof zone === 'object' ? (zone[service] ?? null) : zone
    if (!zoneCode) {
        throw new Error(`Zone tidak ditemukan untuk service '${service}' ke ${country}`)
    }

    // === Chargeable weight & Non-Standard Fees ===
    let dimWeight = 0
    let chargeableWeight = 0
    const nonstandardFees = []
    const notes = [
        ...switchNotes,
        ...(isDemandActive() ? [] : ['Demand Surcharge belum berlaku (efektif 21 Sep 2026)']),
    ]

    if (request.packages && request.packages.length > 0 && !isFreight(service)) {
        const cwtCalc = computeShipmentChargeableWeight(request.packages)
        chargeableWeight = cwtCalc.total_chargeable_weight_kg
        request.packages.forEach(pkg => {
            const chk = checkPackageSurcharge(pkg.length_cm, pkg.width_cm, pkg.height_cm, pkg.weight_kg, pkg)
            if (chk.charge > 0) {
                nonstandardFees.push({ label: `${chk.label} (${pkg.label || 'Package'})`, amount: chk.charge })
            }
        })
    } else if (request.freight_units && request.freight_units.length > 0 && isFreight(service)) {
        const cwtCalc = computeFreightChargeableWeight(request.freight_units)
        chargeableWeight = cwtCalc.total_chargeable_weight_kg
        request.freight_units.forEach(unit => {
            const chk = checkFreightSurcharge(unit.length_cm, unit.weight_kg, unit.width_cm, unit.height_cm, unit.non_stackable)
            if (chk.charge > 0) {
                nonstandardFees.push({ label: `${chk.label} (${unit.label || 'Freight Unit'})`, amount: chk.charge })
            }
            if (chk.notes && chk.notes.length > 0) notes.push(...chk.notes)
        })
    } else {
        if (request.dimensions_cm?.length === 3) {
            dimWeight = calculateDimWeight(
                request.dimensions_cm[0],
                request.dimensions_cm[1],
                request.dimensions_cm[2]
            )
        }

        const minWeight = isFreight(service) ? MINIMUM_FREIGHT_WEIGHT_KG : MINIMUM_BILLED_WEIGHT_KG
        chargeableWeight = Math.max(request.weight_kg, dimWeight, minWeight)

        // Surcharge single package / freight unit jika dimensi diisi
        if (request.dimensions_cm?.length === 3 && !isFreight(service)) {
            const chk = checkPackageSurcharge(
                request.dimensions_cm[0],
                request.dimensions_cm[1],
                request.dimensions_cm[2],
                request.weight_kg,
                request.extra || {}
            )
            if (chk.charge > 0) {
                nonstandardFees.push({ label: chk.label, amount: chk.charge })
            }
        } else if (isFreight(service) && request.dimensions_cm) {
            const chk = checkFreightSurcharge(
                request.dimensions_cm[0],
                request.weight_kg,
                request.dimensions_cm[1],
                request.dimensions_cm[2],
                request.extra?.non_stackable || false
            )
            if (chk.charge > 0) {
                nonstandardFees.push({ label: chk.label, amount: chk.charge })
            }
            if (chk.notes && chk.notes.length > 0) notes.push(...chk.notes)
        }
    }

    // === Base rate ===
    let basePrice = calculateBase(request.rate_type, service, direction, zoneCode, chargeableWeight)
    if (basePrice === null) {
        throw new Error(
            `Tidak ada rate tersedia: direction='${direction}' service='${service}' ` +
            `zone='${zoneCode}' weight=${chargeableWeight}kg (FedEx)`
        )
    }

    // === Discount ===
    let discount = 0
    if (request.discount_pct) {
        discount = pyRound(basePrice * (request.discount_pct / 100))
    }
    const discountedBase = basePrice - discount

    // === Surcharges ===
    const surcharges = {}

    // Non-Standard Fees
    nonstandardFees.forEach(fee => {
        surcharges[fee.label] = pyRound(fee.amount)
    })

    // Demand Surcharge (per-region, tanggal efektif 21 Sep 2026)
    const demand = computeDemandSurcharge(service, direction, country, chargeableWeight)
    if (demand > 0) {
        surcharges['Demand Surcharge'] = demand
    }

    // ODA/OPA Surcharge
    const svcType = isFreight(service) ? 'freight' : 'parcel'

    const indoPostal = isImport
        ? (request.postal_code_destination ?? null)
        : (request.postal_code_origin ?? null)
    const indoCity   = request.extra?.indonesia_city ?? null
    const indoKind   = isImport ? 'oda' : 'opa'
    const indoResult = lookupAndCompute(
        indoKind, svcType, 'Indonesia', indoPostal, indoCity, chargeableWeight
    )
    let odaApplied = false
    if (indoResult.charge > 0) {
        surcharges[`${indoKind.toUpperCase()} Surcharge (${indoResult.tier}) - Indonesia`] =
            pyRound(indoResult.charge)
        if (indoKind === 'oda') odaApplied = true
    }

    const foreignPostal = isImport
        ? (request.postal_code_origin ?? null)
        : (request.postal_code_destination ?? null)
    const foreignCity   = request.extra?.foreign_city ?? null
    const foreignKind   = isImport ? 'opa' : 'oda'
    if (foreignPostal || foreignCity) {
        const foreignResult = lookupAndCompute(
            foreignKind, svcType, country, foreignPostal, foreignCity, chargeableWeight
        )
        if (foreignResult.charge > 0) {
            surcharges[`${foreignKind.toUpperCase()} Surcharge (${foreignResult.tier}) - ${country}`] =
                pyRound(foreignResult.charge)
            if (foreignKind === 'oda') odaApplied = true
        }
    }

    // Special Handling Fees
    if (request.special_handling) {
        const shResult = computeSpecialHandling(
            service, direction, country, chargeableWeight,
            { oda_applied: odaApplied, ...request.special_handling }
        )
        shResult.components.forEach(c => {
            surcharges[c.label] = pyRound(c.amount)
        })
        if (shResult.notes && shResult.notes.length > 0) {
            notes.push(...shResult.notes)
        }
    }

    // Fuel Surcharge
    const fsiPct = request.extra?.fsi_pct
    if (fsiPct) {
        let fsiBasis = discountedBase
        for (const v of Object.values(surcharges)) fsiBasis += v
        surcharges[`Fuel Surcharge (${fsiPct}%)`] = pyRound(fsiBasis * (fsiPct / 100))
    }

    // === Total ===
    let totalSurcharges = 0
    for (const v of Object.values(surcharges)) totalSurcharges += v

    const total = pyRound(discountedBase + totalSurcharges)

    return {
        carrier: 'fedex',
        rate_type: request.rate_type,
        service: service,
        zone: zoneCode,
        base_price: pyRound(basePrice),
        surcharges: surcharges,
        discount: pyRound(discount),
        total: total,
        currency: 'IDR',
        notes: notes,
        extra: {
            chargeable_weight: chargeableWeight,
            dim_weight: dimWeight
        }
    }
}

export default { calculate }
