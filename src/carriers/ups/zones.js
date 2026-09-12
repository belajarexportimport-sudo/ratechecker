import { ZONE_INDEX } from './zones_data.js'

export const CHINA_SOUTHERN_RANGES = [
    { start: 51, end: 53 },
    { start: 35, end: 36 }
]

export function isChinaSouthern(postalCode) {
    if (!postalCode) return false;
    const digits = postalCode.replace(/\D/g, '');
    if (digits.length < 2) return false;
    const prefix2 = parseInt(digits.slice(0, 2), 10);
    return CHINA_SOUTHERN_RANGES.some(r => prefix2 >= r.start && prefix2 <= r.end);
}

const UPS_COUNTRY_ALIASES = {
    'cina': 'china',  // ejaan Indonesia -- sinkron dgn alias FedEx
}

export function findCountry(name) {
    let key = name.trim().toLowerCase()
    key = UPS_COUNTRY_ALIASES[key] || key
    if (ZONE_INDEX[key]) return ZONE_INDEX[key]
    
    const matches = Object.entries(ZONE_INDEX).filter(([k, v]) => k.includes(key) || key.includes(k))
    if (matches.length === 1) return matches[0][1]
    if (matches.length > 1) {
        throw new Error(`Negara '${name}' ambigu (UPS).`)
    }
    throw new Error(`Negara '${name}' tidak ditemukan di UPS Zone Index.`)
}

export function effectiveCountryForZone(country, postalCode = null) {
    // Sama seperti normalisasi internal getZone() (china -> "cn southern"),
    // tapi diekspos supaya caller lain (calculator.js) bisa pakai nama yang
    // SUDAH disesuaikan itu utk named-group override commercial rate
    // A26/B26 (lihat rates/index.js getGroupKey()) -- kalau tidak, shipment
    // China dengan kode pos Southern (Guangdong/Fujian) salah match ke
    // grup "rest of china" (nilai zone 3) padahal seharusnya "china south"
    // (nilai zone 10), walau zone sendiri sudah benar resolve ke 10.
    const key = country.trim().toLowerCase()
    if (key === "china" && postalCode && isChinaSouthern(postalCode)) {
        return "cn southern"
    }
    return country
}

export function getZone(country, direction, service, postalCode = null) {
    let effectiveCountry = country.trim().toLowerCase()
    if (effectiveCountry === "china" && postalCode && isChinaSouthern(postalCode)) {
        effectiveCountry = "cn southern"
    }
    
    const cdata = findCountry(effectiveCountry)
    const keyMap = {
        "export_saver": "saverExport",
        "export_expedited": "expeditedExport",
        "export_wwef": "wwefExport",
        "import_saver": "saverImport",
        "import_expedited": "expeditedImport",
        "import_wwef": "wwefImport",
    }
    
    const field = keyMap[`${direction}_${service}`]
    if (!field) throw new Error(`Kombinasi direction='${direction}' service='${service}' tidak valid.`)
    
    let zone = cdata[field]
    if (zone === null && service === "wwef") {
        zone = cdata[direction === "export" ? "saverExport" : "saverImport"]
    }
    
    return zone
}
