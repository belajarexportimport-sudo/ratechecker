/**
 * UPS EAS/RAS lookup -- port dari calculator-ups/zip_screening_lib.js (versi
 * lain dari kalkulator UPS milik user sendiri) yang sudah lebih dulu
 * mengimplementasikan ini. Logika normalisasi & pencarian range/kota
 * disederhanakan (dihapus dependensi DOM/document, versi tanggal APR26 --
 * lihat catatan di eas_ras_data.js) tapi ATURAN MATCH-nya dijaga sama persis.
 */
import { EAS_RAS_DATA, EAS_RAS_CITIES } from './eas_ras_data.js'

const COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "uae": "United Arab Emirates",
    "korea": "South Korea",
    "south korea": "South Korea",
    "taiwan, china": "Taiwan",
    "taiwan": "Taiwan",
    "hong kong, china": "Hong Kong",
    "hong kong": "Hong Kong",
    "macau, china": "Macau",
    "macau": "Macau",
}

function normalizeZip(country, zip) {
    if (!zip) return ""
    let cleanZip = zip.toString().trim().replace(/[\s-]+/g, '')
    const countryLower = country.toLowerCase().trim()
    if (countryLower === 'united states' || countryLower === 'usa' || countryLower === 'us') {
        const numericOnly = cleanZip.replace(/[^0-9]/g, '')
        cleanZip = numericOnly.length > 5 ? numericOnly.substring(0, 5) : numericOnly
    }
    return cleanZip
}

function resolveCountryKey(dataObj, country) {
    if (dataObj[country]) return country
    const lower = country.toLowerCase().trim()
    const matched = Object.keys(dataObj).find(k => k.toLowerCase().trim() === lower)
    return matched || null
}

/**
 * @param {string} country
 * @param {string} zip - kode pos (boleh kosong)
 * @param {string} city - nama kota (boleh kosong, dipakai sbg fallback kalau
 *   negaranya tidak punya sistem kode pos baku, mis. banyak negara Afrika/Karibia)
 * @param {'origin'|'destination'} context
 * @returns {'EAS'|'RAS'|null}
 */
export function lookupEasRas(country, zip, city, context) {
    if (!country) return null

    const aliasKey = country.toLowerCase().trim()
    const effectiveCountry = COUNTRY_ALIASES[aliasKey] || country
    const effectiveZip = normalizeZip(effectiveCountry, zip)
    const cityTrimmed = city ? city.trim() : ""

    // 1. RANGE LOOKUP (kode pos)
    const rangeKey = resolveCountryKey(EAS_RAS_DATA, effectiveCountry)
    if (rangeKey && effectiveZip) {
        const ranges = EAS_RAS_DATA[rangeKey]
        const zipStr = effectiveZip.toUpperCase()
        const zipNum = parseInt(zipStr.replace(/[^0-9]/g, ''), 10)
        for (const range of ranges) {
            const { low, high } = range
            const isNumericRange = !isNaN(parseFloat(low)) && isFinite(low) && !isNaN(parseFloat(high)) && isFinite(high)
            let isMatch = false
            if (isNumericRange) {
                if (!isNaN(zipNum) && zipNum >= parseInt(low, 10) && zipNum <= parseInt(high, 10)) isMatch = true
            } else {
                const lo = low.toString().toUpperCase()
                const hi = high.toString().toUpperCase()
                if (zipStr >= lo && zipStr <= (hi + "\uffff")) isMatch = true
            }
            if (isMatch) {
                const result = context === 'origin' ? range.originType : range.destType
                if (result) return result
            }
        }
    }

    // 2. CITY LOOKUP (fallback, negara tanpa kode pos baku)
    if (cityTrimmed.length > 1) {
        const cityKey = resolveCountryKey(EAS_RAS_CITIES, country)
        if (cityKey) {
            const searchCity = cityTrimmed.toLowerCase()
            const matched = EAS_RAS_CITIES[cityKey].find(c => c.name.toLowerCase().trim() === searchCity)
            if (matched) {
                const result = context === 'origin' ? matched.originType : matched.destType
                if (result) return result
            }
        }
    }

    return null
}
