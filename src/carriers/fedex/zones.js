import { ZONE_INDEX, COMMERCIAL_ZONE_INDEX } from './zones_data.js'

// ---------------------------------------------------------------------------
// China: sesuai fedex-rates-zi-en-id-2026.pdf & Zone Chart Exsis, negara
// "China" dipecah berdasarkan kode pos:
//   - Fujian     350000-369999 -> "South"
//   - Guangdong  510000-529999 -> "South"
//   - Selain itu                -> "Excluding South" (default)
// Range EKSAK (bukan 2-digit-prefix) -- prefix "51"/"52"/"53" yang dipakai
// sebelumnya salah, ikut memasukkan 530000-539999 yang BUKAN Guangdong.
// ---------------------------------------------------------------------------
const CHINA_SOUTH_RANGES = [
    [350000, 369999],
    [510000, 529999],
]

/**
 * Return true kalau postalCode (string) jatuh di range Fujian/Guangdong
 * ("South"), false kalau tidak/format tidak dikenali -> caller pakai
 * default ("Excluding South").
 */
export function isChinaSouth(postalCode) {
    if (!postalCode) return false
    const p = String(postalCode).trim().replace(/\s+/g, '')
    if (!/^\d+$/.test(p)) return false
    const pInt = parseInt(p, 10)
    return CHINA_SOUTH_RANGES.some(([begin, end]) => pInt >= begin && pInt <= end)
}

// Alias kecil utk publish -- 'united states' polos ambigu di Zone Index
// (ada 2 baris: '(Rest of Country)' & '(Western Region)'), TAPI keduanya
// selalu zone yang SAMA (D) baik export maupun import, jadi aman
// didefaultkan tanpa risiko salah harga.
const PUBLISH_ALIASES = {
    'united states': 'united states (rest of country)',
    'usa': 'united states (rest of country)',
    'us': 'united states (rest of country)',
}

export function findCountry(name) {
    const key = PUBLISH_ALIASES[name.trim().toLowerCase()] || name.trim().toLowerCase()
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
    const key = country.trim().toLowerCase()

    // China: Zone Index PUBLISH cuma py 1 baris "china" (default zone C),
    // TIDAK ada baris Fujian/Guangdong terpisah spt di Commercial -> kalau
    // kode pos masuk area South, override HASIL zone letter jadi "B" langsung
    // (sesuai fedex-rates-zi-en-id-2026.pdf), BUKAN ganti effectiveCountry
    // jadi 'fujian'/'guangdong' (itu bug lama -- ZONE_INDEX publish tidak
    // punya key itu, selalu throw 'not found').
    if (key === 'china' && isChinaSouth(postalCode)) {
        return 'B'
    }

    const cdata = findCountry(key)
    const zone = isImport ? cdata.import : cdata.export
    if (!zone) {
        throw new Error(`Direction ${isImport ? 'import' : 'export'} tidak tersedia untuk ${country} (FedEx Publish)`)
    }
    return zone
}

// Alias nama negara: input user (gaya Zone Index publish/README) -> nama
// PERSIS di Zone Index commercial (Exsis). Cuma dibutuhkan utk negara yg
// ejaan/pengelompokannya beda antara 2 sumber data (~30 negara dari 229).
// TANPA tabel ini, negara2 umum (United States, Philippines, China, Korea,
// dst) TIDAK PERNAH ketemu di Commercial Zone Index -> "rate commercial
// tidak muncul" utk hampir semua negara yang sering dites.
const COMMERCIAL_ALIASES = {
    'grand cayman': 'cayman islands',
    'great thatch island': 'british virgin islands',
    'great tobago islands': 'british virgin islands',
    'jost van dyke islands': 'british virgin islands',
    'montserrat': 'monserrat',
    'norman island': 'british virgin islands',
    'philippines': 'phillipines',
    'reunion': 'réunion',
    'rota': 'northern mariana islands',
    'saipan': 'northern mariana islands',
    'tinian': 'northern mariana islands',
    'slovak republic': 'slovakia',
    'st. christopher': 'st. kitts and nevis',
    'st. kitts & nevis': 'st. kitts and nevis',
    'st. croix island': 'u.s. virgin islands',
    'st. john': 'u.s. virgin islands',
    'st. thomas': 'u.s. virgin islands',
    'st. lucia': 'saint lucia',
    'tahiti': 'french polynesia',
    'tortola island': 'british virgin islands',
    'union island': 'st. vincent & the grenadines',
    'united states (rest of country)': 'u.s.a.',
    'united states (western region)': 'u.s.a.',
    'usa': 'u.s.a.',
    'united states': 'u.s.a.',
    'korea': 'south korea',
    'ivory coast': "côte d'ivoire (ivory coast)",
    'moldova': 'republic of moldova',
    'tanzania': 'united republic of tanzania',
    'uae': 'united arab emirates',
    'united kingdom': 'united kingdom (great britain)',
    'great britain': 'united kingdom (great britain)',
    'macau': 'macau sar, china',
    'hong kong': 'hong kong sar, china',
    'congo dem rep of': 'democratic republic of the congo',
}

// Negara yang ADA di Zone Index publish tapi TIDAK punya rate commercial
// (Exsis) sama sekali -> raise error jelas, bukan silent fallback.
const COMMERCIAL_UNAVAILABLE_COUNTRIES = new Set([
    'canary islands', 'channel islands', 'norfolk island', 'san marino',
    'st. barthelemy', 'st. eustatius', 'vatican city', 'saba',
])

export function findCountryCommercial(name, isImport) {
    const dirKey = isImport ? 'import' : 'export'
    const index = COMMERCIAL_ZONE_INDEX[dirKey]
    if (!index) throw new Error(`Direction ${dirKey} tidak valid untuk Commercial Zone Index.`)

    let key = name.trim().toLowerCase()
    if (COMMERCIAL_UNAVAILABLE_COUNTRIES.has(key)) {
        throw new Error(`Commercial rate (Exsis) tidak tersedia utk negara '${name}' -> pakai rate_type='publish' saja utk negara ini.`)
    }
    key = COMMERCIAL_ALIASES[key] || key

    if (index[key]) return index[key]

    const matches = Object.entries(index).filter(([k]) => k.includes(key))
    if (matches.length === 1) return matches[0][1]
    if (matches.length > 1) {
        const names = matches.map(([, v]) => v.display_name).join(', ')
        throw new Error(`Negara '${name}' ambigu di Commercial Zone Index, cocok dgn: ${names}`)
    }
    throw new Error(
        `Negara '${name}' tidak ditemukan di FedEx Commercial Zone Index arah '${dirKey}'. ` +
        `Kemungkinan: (a) ejaan beda dari Zone Index publish -> tambahkan ke COMMERCIAL_ALIASES, ` +
        `atau (b) memang belum ada rate commercial utk negara ini -> pakai rate_type='publish'.`
    )
}

/**
 * Return object zone commercial {display_name, IP, IE, IPF, IEF} utk
 * country+direction. China ditangani khusus (Zone Chart Exsis memecah China
 * jadi 2 baris "China (South)" / "China (Excluding China South)"
 * berdasarkan kode pos Fujian/Guangdong, BUKAN 1 baris "China").
 */
export function getZoneCommercial(country, isImport, postalCode = null, city = null) {
    const nameKey = country.trim().toLowerCase()
    const dirKey = isImport ? 'import' : 'export'

    if (nameKey === 'china') {
        const label = isChinaSouth(postalCode) ? 'china (south)' : 'china (excluding china south)'
        const entry = COMMERCIAL_ZONE_INDEX[dirKey][label]
        if (!entry) {
            throw new Error(`Zone commercial utk '${label}' tidak ditemukan (arah ${dirKey}).`)
        }
        return entry
    }

    return findCountryCommercial(nameKey, isImport)
}