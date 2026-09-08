"""
FedEx Indonesia Rate Calculator - rate_common.py
==================================================
Util & "pricing engine" yang DIPAKAI BERSAMA oleh rates_promotional.py dan
rates_commercial.py, supaya nambah rate_type baru di masa depan (rate_type
ke-3, ke-4, dst) cukup bikin 1 file baru `rates_<nama>.py` yang import modul
ini, TANPA perlu sentuh/duplikasi logic pricing yang sudah ada.

Isi modul ini SENGAJA rate_type-agnostic (tidak tahu apa itu "promotional"
atau "commercial") -> semua yang spesifik per rate_type (Zone Index, tabel
rate, alias negara) tetap di modul masing-masing.

Dipindah dari rates.py (sebelumnya 1 file besar 2000+ baris gabungan
promotional + commercial) agar lebih scalable & gampang di-maintain per
rate_type. Lihat rates.py (façade tipis) utk API publik yang dipakai
calculator.py/app.py - TIDAK ada perubahan behavior, cuma reorganisasi file.
"""

from bisect import bisect_right


class FedExRateError(Exception):
    pass


LEG_TYPES = ["door_to_door", "door_to_airport", "airport_to_door", "airport_to_airport"]


# ---------------------------------------------------------------------------
# China: sesuai fedex-rates-zi-en-id-2026.pdf hal.1 (dan Zone Chart Exsis yang
# ternyata pakai pembagian sama), negara "China" dipecah jadi beberapa Zone
# berdasarkan kode pos:
#   - Fujian     350000-369999 -> "South"
#   - Guangdong  510000-529999 -> "South"
#   - Selain itu                -> "Excluding South" (default)
# Range post code-nya SAMA utk promotional & commercial (makanya di sini,
# bukan di modul masing2) -> yang beda cuma HURUF zone/nama baris yang
# dipakai per rate_type (itu urusan modul masing2, lihat get_zone() /
# get_zone_commercial()).
# ---------------------------------------------------------------------------
_CHINA_SOUTH_RANGES = [
    (350000, 369999, "China (South) - Fujian"),
    (510000, 529999, "China (South) - Guangdong"),
]


def resolve_china_zone(postal_code):
    """
    postal_code: string kode pos China (6 digit).
    Return (True, region_label) kalau kode pos jatuh di Fujian/Guangdong
    ("South"), atau (None, None) kalau tidak/format tidak dikenali -> caller
    tetap pakai default ("Excluding South").
    NB: dulu return value pertama adalah literal zone letter promotional
    ("B"). Sekarang cuma truthy flag generik supaya rate_type-agnostic -
    modul masing2 yang menerjemahkan jadi huruf zone/nama baris sendiri.
    """
    if not postal_code:
        return None, None
    p = postal_code.strip().replace(" ", "")
    if not p.isdigit():
        return None, None
    p_int = int(p)
    for begin, end, label in _CHINA_SOUTH_RANGES:
        if begin <= p_int <= end:
            return True, label
    return None, None


# ---------------------------------------------------------------------------
# Parser tabel rate mentah (format CSV inline) -> dipakai oleh SEMUA rate_type,
# `zones` WAJIB diisi (daftar huruf/kode zone rate_type itu) - tidak ada
# default diam-diam supaya tidak salah pakai daftar zone rate_type lain.
# ---------------------------------------------------------------------------

def parse_doc_table(csv_text, zones):
    """Format baris: 'weight,<rate per zone berurutan>' - step 0.5kg (IP/IE)."""
    table = {}
    for line in csv_text.strip().splitlines():
        parts = line.split(",")
        w = float(parts[0])
        rates = [int(x) for x in parts[1:]]
        table[w] = dict(zip(zones, rates))
    return table


def parse_band_table(csv_text, zones):
    """Format baris: 'label,min_kg,<rate per zone berurutan>' (IPF/IEF & >20kg IP/IE)."""
    bands = []
    for line in csv_text.strip().splitlines():
        parts = line.split(",")
        label = parts[0]
        min_kg = float(parts[1])
        rates = [int(x) for x in parts[2:]]
        bands.append((min_kg, label, dict(zip(zones, rates))))
    bands.sort(key=lambda b: b[0])
    return bands


def parse_flat_table(csv_text, zones):
    """Tabel flat sekali baris (dipakai Envelope & Pak per titik berat)."""
    table = {}
    for line in csv_text.strip().splitlines():
        parts = line.split(",")
        w = float(parts[0])
        rates = [int(x) for x in parts[1:]]
        table[w] = dict(zip(zones, rates))
    return table


def round_up_1000(value):
    return int(-(-value // 1000) * 1000)


# ---------------------------------------------------------------------------
# Pricing engine - generik, SAMA untuk semua rate_type. Yang beda antar
# rate_type cuma isi `table` & `zone` yang dikirim caller (lihat
# rates_promotional.calculate_base() / rates_commercial.calculate_base()).
# ---------------------------------------------------------------------------

def price_from_table(table, zone, service, weight_kg, leg_type="door_to_door",
                      apply_minimum=True, round_invoice=True):
    """
    table : dict rate utk 1 kombinasi (rate_type, direction, service) dgn
            shape {"envelope":.., "pak":.., "doc":.., "band":.., "min_kg":..,
            "has_legs": bool}. Ini shape yang sama dipakai RATES (promotional)
            & COMMERCIAL_RATES (commercial) -> makanya engine ini bisa dipakai
            bareng tanpa tahu rate_type-nya apa.
    zone  : huruf/kode zone yang SUDAH diresolve caller (rate_type-specific).

    Return dict: {"mode", "price", "price_invoice"?, "billed_weight_kg",
    "leg_type_used", "min_kg_note"} - BELUM ada service/direction/country/
    notes-lain/currency/rate_type, itu ditambah oleh caller (lihat modul
    rates_promotional.py / rates_commercial.py).
    """
    min_kg = table["min_kg"]
    billed_weight = weight_kg
    min_kg_note = None

    if apply_minimum and min_kg and weight_kg < min_kg:
        billed_weight = min_kg
        min_kg_note = (f"Berat di bawah minimum {min_kg}kg -> dibulatkan ke "
                        f"{min_kg}kg (kebijakan FedEx untuk IPF/IEF).")

    if table.get("has_legs"):
        if leg_type not in LEG_TYPES:
            raise FedExRateError(f"leg_type '{leg_type}' tidak dikenal. Pilihan: {LEG_TYPES}")
        bands = table["band"][leg_type]
    else:
        bands = table["band"]

    result = None

    # 0) FedEx Envelope: hanya utk IP, actual weight <= 0.5kg, single piece
    if service == "IP" and table["envelope"] and billed_weight <= 0.5:
        price = table["envelope"][0.5][zone]
        result = {"mode": "fedex_envelope", "price": price}

    # 1) FedEx Pak: hanya utk IP, actual weight 0.5-2.5kg
    elif service == "IP" and table["pak"] and 0.5 < billed_weight <= 2.5:
        pak_table = table["pak"]
        steps = sorted(pak_table.keys())
        idx = bisect_right(steps, billed_weight - 1e-9)
        idx = min(idx, len(steps) - 1)
        step = steps[idx]
        price = pak_table[step][zone]
        result = {"mode": "fedex_pak", "step_used_kg": step, "price": price}

    # 2) Tabel dokumen bertahap 0.5kg (IP & IE, sampai 20.5kg)
    elif table["doc"] is not None and billed_weight <= 20.5:
        doc_table = table["doc"]
        steps = sorted(doc_table.keys())
        idx = bisect_right(steps, billed_weight - 1e-9)
        idx = min(idx, len(steps) - 1)
        step = steps[idx]
        price = doc_table[step][zone]
        result = {"mode": "flat_rate_per_shipment", "step_used_kg": step, "price": price}

    else:
        # 3) Tabel per-kg (band) - dipakai IPF/IEF selalu, dan IP/IE di atas 20.5kg
        chosen = None
        for min_band, label, rates in bands:
            if billed_weight >= min_band:
                chosen = (label, rates)
        if chosen is None:
            raise FedExRateError("Berat tidak masuk ke band manapun (cek input).")
        label, rates = chosen
        per_kg = rates[zone]
        price = per_kg * billed_weight
        result = {"mode": "per_kg", "band": label, "rate_per_kg": per_kg, "price": price}

    if round_invoice:
        result["price_invoice"] = round_up_1000(result["price"])

    result["billed_weight_kg"] = billed_weight
    result["leg_type_used"] = leg_type if table.get("has_legs") else None
    result["min_kg_note"] = min_kg_note
    return result
