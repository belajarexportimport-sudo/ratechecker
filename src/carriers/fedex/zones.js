import { ZONE_INDEX, COMMERCIAL_ZONE_INDEX } from './zones_data.js'

export const CHINA_ZONES = {
    "fujian": "fujian",
    "guangdong": "guangdong",
    "south_china": "south china" // aliasing
}

export function resolveChinaZone(postalCode, city) {
    if (!postalCode) return "china"
    const prefix = postalCode.slice(0, 2)
    if (["51", "52", "53"].includes(prefix)) {
        return CHINA_ZONES.guangdong
    }
    if (["35", "36"].includes(prefix)) {
        return CHINA_ZONES.fujian
    }
    return "china"
}

export function findCountry(name) {
    const key = name.trim().toLowerCase()
    if (ZONE_INDEX[key]) return ZONE_INDEX[key]
    
    // Fuzzy search
    const matches = Object.entries(ZONE_INDEX).filter(([k, v]) => k.includes(key) || key.includes(k))
    if (matches.length === 1) return matches[0][1]
    if (matches.length > 1) {
        throw new Error(`Negara '${name}' ambigu (FedEx Publish).`)
    }
    throw new Error(`Negara '${name}' tidak ditemukan di FedEx Publish Zone Index.`)
}

export function getZone(country, isImport, postalCode = null, city = null) {
    let effectiveCountry = country.trim().toLowerCase()
    if (effectiveCountry === "china" && postalCode) {
        effectiveCountry = resolveChinaZone(postalCode, city)
    }
    
    const cdata = findCountry(effectiveCountry)
    const zone = isImport ? cdata.import : cdata.export
    if (!zone) {
        throw new Error(`Direction ${isImport ? 'import' : 'export'} tidak tersedia untuk ${country} (FedEx Publish)`)
    }
    return zone
}

export function findCountryCommercial(name, isImport) {
    const dirKey = isImport ? 'import' : 'export'
    const index = COMMERCIAL_ZONE_INDEX[dirKey]
    if (!index) throw new Error(`Direction ${dirKey} tidak valid untuk Commercial Zone Index.`)

    const key = name.trim().toLowerCase()
    if (index[key]) return index[key]
    
    const matches = Object.entries(index).filter(([k, v]) => k.includes(key) || key.includes(k))
    if (matches.length === 1) return matches[0][1]
    if (matches.length > 1) {
        throw new Error(`Negara '${name}' ambigu (FedEx Commercial).`)
    }
    throw new Error(`Negara '${name}' tidak ditemukan di FedEx Commercial Zone Index.`)
}

export function getZoneCommercial(country, isImport, postalCode = null, city = null) {
    let effectiveCountry = country.trim().toLowerCase()
    if (effectiveCountry === "china" && postalCode) {
        effectiveCountry = resolveChinaZone(postalCode, city)
    }
    
    const cdata = findCountryCommercial(effectiveCountry, isImport)
    return cdata
}
