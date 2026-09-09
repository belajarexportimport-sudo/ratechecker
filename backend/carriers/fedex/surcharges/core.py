"""
FedEx Indonesia Rate Calculator - Tahap 2 (surcharges.py)
===========================================================
Berisi nominal IDR untuk surcharge ODA/OPA per tier (dari
fedex-rates-sur-en-id-2026.pdf, "Surcharge and Other Information - Indonesia").

Fuel surcharge & Demand surcharge SENGAJA tidak dihardcode sebagai konstanta:
- Fuel surcharge % berubah tiap Senin (harus jadi parameter input manual).
- Demand surcharge per kg juga bisa berubah sewaktu-waktu (contoh:
  demand_surcharge_update_4_sep_2026.pdf, efektif 21 Sep 2026, per kg by region).
  Tabelnya disediakan di sini sebagai data terpisah (DEMAND_SURCHARGE_TABLE)
  supaya gampang diganti kalau ada update baru.

CATATAN PENTING soal ODA/OPA (baca sebelum pakai):
- Tier didapat dari lookup di oda_opa.py (database ~67.600 kode pos/kota, 114 negara).
- Kedua sisi shipment SUDAH dicek di calculator.py (bukan cuma sisi Indonesia):
    * indonesia_postal_code/indonesia_city -> sisi Indonesia:
        EXPORT (dari Indonesia)   -> OPA (out-of-PICKUP-area) di Indonesia.
        IMPORT/ImportOne (ke Indonesia) -> ODA (out-of-DELIVERY-area) di Indonesia.
    * foreign_postal_code -> sisi negara lawan:
        EXPORT -> ODA (delivery) di negara tujuan.
        IMPORT -> OPA (pickup) di negara asal.
  Catatan: sisi negara lawan HANYA dicek kalau `foreign_postal_code` diisi
  oleh caller -- kalau kosong, sisi itu tidak dihitung (bisa under-estimate;
  lihat notes yang dihasilkan calculator.py).
"""

import datetime

# Tarif OPA (Out-of-Pickup-Area) per tier, dari surcharge sheet Indonesia.
# Tier A: tidak berlaku untuk OPA (hanya utk ODA).
OPA_TARIFF = {
    "No": {"per_shipment": 0, "per_kg": 0},
    "A": {"per_shipment": 0, "per_kg": 0},   # not applicable
    "B": {"per_shipment": 339000, "per_kg": 6000},
    "C": {"per_shipment": 442000, "per_kg": 8000},
}

# Tarif ODA (Out-of-Delivery-Area) per tier, dari surcharge sheet Indonesia.
ODA_TARIFF = {
    "No": {"per_shipment": 0, "per_kg": 0},
    "A": {"per_shipment": 52000, "per_kg": 0},   # flat, tidak ada opsi per kg
    "B": {"per_shipment": 339000, "per_kg": 6000},
    "C": {"per_shipment": 442000, "per_kg": 8000},
}


def compute_oda_opa_charge(kind, tier, weight_kg):
    """
    kind      : 'opa' | 'oda'
    tier      : 'No' | 'A' | 'B' | 'C' (hasil lookup oda_opa.py, tanpa prefix 'Tier ')
    weight_kg : billed weight, dipakai utk opsi 'per kg' (ambil yang lebih besar
                dibanding 'per shipment', sesuai aturan "whichever is greater")
    """
    kind = kind.lower()
    tariff_table = OPA_TARIFF if kind == "opa" else ODA_TARIFF
    tier = tier or "No"
    if tier not in tariff_table:
        tier = "No"
    t = tariff_table[tier]
    per_shipment = t["per_shipment"]
    per_kg_total = t["per_kg"] * weight_kg
    charge = max(per_shipment, per_kg_total)
    return {
        "kind": kind.upper(),
        "tier": tier,
        "per_shipment_component": per_shipment,
        "per_kg_component": per_kg_total,
        "charge": charge,
    }


# ---------------------------------------------------------------------------
# Demand Surcharge (per kg, IDR) - efektif 21 September 2026
# Sumber: demand_surcharge_update_4_sep_2026.pdf, tabel "Export/ImportOne"
# Minimum IDR 4.200 per shipment berlaku terlepas dari origin market.
# ---------------------------------------------------------------------------
DEMAND_SURCHARGE_MIN_PER_SHIPMENT = 4200
DEMAND_SURCHARGE_EFFECTIVE_DATE = "2026-09-21"
_DEMAND_SURCHARGE_EFFECTIVE_DATE_OBJ = datetime.date.fromisoformat(DEMAND_SURCHARGE_EFFECTIVE_DATE)

# key: region/negara tujuan (export) atau asal (import) -> per kg IDR
# Priority = service IP/IPF/Envelope/Pak dkk; Economy = IE/IEF.
# (Untuk region yang rate-nya sama utk priority & economy, keduanya diisi sama.)
DEMAND_SURCHARGE_TABLE = {
    "export": {
        # region -> {"priority": per_kg, "economy": per_kg}
        "Australia, Fiji, New Zealand": {"priority": 8400, "economy": 8400},
        "Vietnam": {"priority": 0, "economy": 0},
        "Asia": {"priority": 3000, "economy": 3000},
        "United States (U.S.) and Puerto Rico": {"priority": 26800, "economy": 20100},
        "Canada": {"priority": 26800, "economy": 20100},
        "Mexico": {"priority": 26800, "economy": 20100},
        "Latin America and Caribbean (LAC)": {"priority": 26800, "economy": 20100},
        "Israel": {"priority": 21800, "economy": 21800},
        "Europe": {"priority": 21800, "economy": 21800},
        "India": {"priority": 1800, "economy": 1800},
        "MEISA Group 1": {"priority": 25600, "economy": 25600},
        "MEISA Group 2": {"priority": 41900, "economy": 41900},
    },
    "import": {
        "Australia, Fiji, New Zealand": {"priority": 3000, "economy": 3000},
        "Vietnam": {"priority": 0, "economy": 0},
        "Asia": {"priority": 3000, "economy": 3000},
        "United States (U.S.) and Puerto Rico": {"priority": 0, "economy": 0},
        "Canada": {"priority": 0, "economy": 0},
        "Mexico": {"priority": 0, "economy": 0},
        "Latin America and Caribbean (LAC)": {"priority": 0, "economy": 0},
        "Israel": {"priority": 1700, "economy": 1700},
        "Europe": {"priority": 1700, "economy": 1700},
        "India": {"priority": 9200, "economy": 9200},
        "MEISA Group 1": {"priority": 18300, "economy": 18300},
        "MEISA Group 2": {"priority": 18300, "economy": 18300},
    },
}

# Mapping negara -> region demand surcharge.
# Tahap 3: dilengkapi 100% sesuai footnote 1-4 (Asia/Europe/LAC/MEISA) di
# demand_surcharge_update_4_sep_2026.pdf, dicocokkan satu-per-satu dengan nama
# negara persis seperti di ZONE_INDEX (rates.py) supaya lookup tidak meleset.
#
# 3 negara yang ADA di ZONE_INDEX tapi TIDAK disebut di footnote manapun pada
# dokumen demand surcharge (Norfolk Island, Syria, Yemen) SENGAJA dibiarkan
# tidak dipetakan. Dikonfirmasi user (7 Sep 2026): FedEx memang tidak ada
# service ke 3 negara ini, jadi ini BUKAN gap data yang perlu diperbaiki --
# demand surcharge utk negara ini akan ditandai "tidak dihitung" (bukan diam-
# diam pakai region yang salah tebak), dan itu sudah perilaku yang benar.
_DEMAND_SURCHARGE_GROUPS = {
    "Australia, Fiji, New Zealand": [
        "Australia", "Fiji", "New Zealand",
    ],
    "Vietnam": ["Vietnam"],
    "Asia": [
        "American Samoa", "Brunei", "Cambodia", "China", "Cook Islands",
        "East Timor", "French Polynesia", "Guam", "Hong Kong", "Japan", "Laos",
        "Macau", "Malaysia", "Marshall Islands", "Micronesia", "Mongolia",
        "New Caledonia", "Northern Mariana Islands", "Palau", "Papua New Guinea",
        "Philippines", "Rota", "Saipan", "Samoa", "Singapore", "South Korea",
        "Tahiti", "Taiwan", "Thailand", "Tinian", "Tonga", "Vanuatu",
        "Wallis & Futuna",
    ],
    "United States (U.S.) and Puerto Rico": [
        "United States (Rest of Country)", "United States (Western Region)",
        "Puerto Rico",
    ],
    "Canada": ["Canada"],
    "Mexico": ["Mexico"],
    "Latin America and Caribbean (LAC)": [
        "Anguilla", "Antigua", "Argentina", "Aruba", "Bahamas", "Barbados",
        "Barbuda", "Belize", "Bermuda", "Bolivia", "Bonaire", "Brazil",
        "British Virgin Islands", "Cayman Islands", "Chile", "Colombia",
        "Costa Rica", "Curacao", "Dominica", "Dominican Republic", "Ecuador",
        "El Salvador", "French Guiana", "Grand Cayman", "Great Thatch Island",
        "Great Tobago Islands", "Grenada", "Guadeloupe", "Guatemala", "Guyana",
        "Haiti", "Honduras", "Jamaica", "Jost Van Dyke Islands", "Martinique",
        "Montserrat", "Nevis", "Nicaragua", "Norman Island", "Panama",
        "Paraguay", "Peru", "Saba", "St. Barthelemy", "St. Christopher",
        "St. Croix Island", "St. Eustatius", "St. John", "St. Kitts & Nevis",
        "St. Lucia", "St. Maarten", "St. Martin", "St. Thomas", "St. Vincent",
        "Suriname", "Tortola Island", "Trinidad & Tobago",
        "Turks & Caicos Islands", "U.S. Virgin Islands", "Union Island",
        "Uruguay", "Venezuela",
    ],
    "Israel": ["Israel"],
    "Europe": [
        "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
        "Belgium", "Bosnia-Herzegovina", "Bulgaria", "Canary Islands",
        "Channel Islands", "Croatia", "Cyprus", "Czech Republic", "Denmark",
        "Estonia", "Faeroe Islands", "Finland", "France", "Georgia", "Germany",
        "Gibraltar", "Greece", "Greenland", "Hungary", "Iceland", "Ireland",
        "Italy", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg",
        "Macedonia", "Malta", "Moldova", "Monaco", "Montenegro", "Netherlands",
        "Norway", "Poland", "Portugal", "Romania", "Russia", "San Marino",
        "Serbia", "Slovak Republic", "Slovenia", "Spain", "Sweden",
        "Switzerland", "Turkey", "Ukraine", "United Kingdom", "Vatican City",
    ],
    "India": ["India"],
    "MEISA Group 1": [
        "Afghanistan", "Bahrain", "Bangladesh", "Bhutan", "Egypt", "Jordan",
        "Kuwait", "Kyrgyzstan", "Maldives", "Nepal", "Oman",
        "Palestine Autonomous", "Saudi Arabia", "Sri Lanka",
        "United Arab Emirates", "Uzbekistan",
    ],
    "MEISA Group 2": [
        "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
        "Cameroon", "Cape Verde", "Chad", "Congo", "Congo Dem Rep Of",
        "Djibouti", "Eritrea", "Ethiopia", "Gabon", "Gambia", "Ghana",
        "Guinea", "Iraq", "Ivory Coast", "Kazakhstan", "Kenya", "Lebanon",
        "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi", "Mali",
        "Mauritania", "Mauritius", "Morocco", "Mozambique", "Namibia",
        "Niger", "Nigeria", "Pakistan", "Qatar", "Reunion", "Rwanda",
        "Senegal", "Seychelles", "South Africa", "Swaziland", "Tanzania",
        "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe",
    ],
}

DEMAND_SURCHARGE_COUNTRY_TO_REGION = {
    country.lower(): region
    for region, countries in _DEMAND_SURCHARGE_GROUPS.items()
    for country in countries
}


def get_demand_surcharge_region(country_display_name):
    key = country_display_name.strip().lower()
    return DEMAND_SURCHARGE_COUNTRY_TO_REGION.get(key)


def compute_demand_surcharge(direction, service, country_display_name, weight_kg,
                              as_of_date=None):
    """
    direction : 'export' | 'import'
    service   : 'IP' | 'IPF' | 'IE' | 'IEF'  -> IP/IPF pakai kolom 'priority',
                IE/IEF pakai kolom 'economy'
    as_of_date : tanggal (datetime.date) yang dipakai utk cek apakah Demand
                Surcharge SUDAH efektif per DEMAND_SURCHARGE_EFFECTIVE_DATE
                (2026-09-21). Default None -> pakai datetime.date.today().
                Override manual berguna utk quote yang memang ditujukan utk
                tanggal pengiriman di masa depan (setelah efektif), atau utk
                testing.

                PENTING: sebelum fix ini, fungsi ini TIDAK PERNAH mengecek
                tanggal sama sekali -> Demand Surcharge selalu dihitung
                walau hari ini masih SEBELUM tanggal efektifnya (bug nyata,
                bikin over-charge di setiap quote sebelum 21 Sep 2026).
    Return None kalau region tidak dikenal (perlu dilengkapi manual di
    DEMAND_SURCHARGE_COUNTRY_TO_REGION), supaya tidak salah hitung diam-diam.
    """
    if as_of_date is None:
        as_of_date = datetime.date.today()
    if as_of_date < _DEMAND_SURCHARGE_EFFECTIVE_DATE_OBJ:
        return {
            "applied": False,
            "reason": f"Demand Surcharge baru efektif {DEMAND_SURCHARGE_EFFECTIVE_DATE} "
                      f"(as_of_date={as_of_date.isoformat()}) -> belum dihitung.",
            "charge": 0,
        }
    region = get_demand_surcharge_region(country_display_name)
    if region is None:
        return {
            "applied": False,
            "reason": f"Region demand surcharge untuk '{country_display_name}' belum "
                      f"dipetakan di DEMAND_SURCHARGE_COUNTRY_TO_REGION -> surcharge TIDAK dihitung.",
            "charge": 0,
        }
    table = DEMAND_SURCHARGE_TABLE[direction]
    rates = table.get(region)
    if rates is None:
        return {"applied": False, "reason": f"Region '{region}' tidak ada di tabel demand surcharge {direction}.",
                "charge": 0}
    col = "priority" if service in ("IP", "IPF") else "economy"
    per_kg = rates[col]
    charge = max(per_kg * weight_kg, DEMAND_SURCHARGE_MIN_PER_SHIPMENT)
    return {
        "applied": True,
        "region": region,
        "per_kg": per_kg,
        "charge": charge,
        "effective_date": DEMAND_SURCHARGE_EFFECTIVE_DATE,
    }
