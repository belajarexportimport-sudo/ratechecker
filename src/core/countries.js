// =============================================================================
// Daftar negara gabungan (FedEx + UPS) utk autocomplete/dropdown di frontend.
// Ditambahkan sbg respons ke laporan "commercial China tidak muncul" (13 Sep
// 2026) -- ternyata user mengetik "Cina" (ejaan Indonesia), bukan "China".
// Root cause sudah diperbaiki juga (COUNTRY_CODE_ALIASES di fedex/zones.js &
// ups/zones.js), tapi autocomplete ini mencegah SELURUH KELAS masalah salah
// ketik/salah ejaan negara, bukan cuma kasus "Cina" ini saja.
//
// Title-case sederhana dipakai utk key UPS (yang tidak punya display_name
// tersendiri) -- cukup baik utk tampilan dropdown, TIDAK dipakai sbg key
// lookup (lookup tetap pakai lowercase seperti biasa di masing2 zones.js).
// =============================================================================
import { ZONE_INDEX as FEDEX_ZONE_INDEX } from '../carriers/fedex/zones_data.js'
import { ZONE_INDEX as UPS_ZONE_INDEX } from '../carriers/ups/zones_data.js'

function titleCase(str) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase())
}

let _cachedList = null

export function getCountryList() {
    if (_cachedList) return _cachedList

    const seen = new Map() // lowercase key -> display name

    for (const [key, entry] of Object.entries(FEDEX_ZONE_INDEX)) {
        seen.set(key, entry.display_name || titleCase(key))
    }
    for (const key of Object.keys(UPS_ZONE_INDEX)) {
        if (!seen.has(key)) {
            seen.set(key, titleCase(key))
        }
    }

    _cachedList = [...seen.values()].sort((a, b) => a.localeCompare(b))
    return _cachedList
}
