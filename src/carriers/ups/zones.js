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

export function findCountry(name) {
    const key = name.trim().toLowerCase()
    if (ZONE_INDEX[key]) return ZONE_INDEX[key]
    
    const matches = Object.entries(ZONE_INDEX).filter(([k, v]) => k.includes(key) || key.includes(k))
    if (matches.length === 1) return matches[0][1]
    if (matches.length > 1) {
        throw new Error(`Negara '${name}' ambigu (UPS).`)
    }
    throw new Error(`Negara '${name}' tidak ditemukan di UPS Zone Index.`)
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
