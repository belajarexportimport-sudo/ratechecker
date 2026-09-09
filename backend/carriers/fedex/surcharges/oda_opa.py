"""
FedEx ODA / OPA Tier Lookup
===========================
Cari tahu apakah suatu kota/kode pos kena:
- Out-of-Pickup-Area Surcharge (OPA)   -> berlaku saat PENJEMPUTAN
- Out-of-Delivery-Area Surcharge (ODA) -> berlaku saat PENGIRIMAN/DELIVERY
Masing-masing dipecah lagi jadi Parcel Services & Freight Services.

Sumber data: ODA_OPA_tiers_codes.xlsx (114 negara, ~67.600 baris kode pos/kota).
Data mentah sudah diekstrak jadi 'oda_opa_tiers.csv' (satu folder dengan file ini)
supaya loading cepat & tidak butuh openpyxl saat runtime.

File ini CUMA kasih tahu TIER (No / A / B / C), BUKAN nominal surcharge.
Nominal per tier (IDR) sudah ada di backend/carriers/fedex/surcharges/core.py
(compute_oda_opa_charge, sumber: fedex-rates-sur-en-id-2026.pdf).

CATATAN PENTING:
- Kalau negara/kode pos TIDAK ada di data -> kemungkinan besar TIDAK kena
  surcharge ODA/OPA (arealnya dianggap standard), tapi tetap disarankan
  konfirmasi ke FedEx untuk kepastian.
- Sebagian kode pos di sumber asli berupa angka dengan leading zero (misal US
  zip "01002"), itu sudah coba ditangani. Untuk negara dengan format campuran/
  tidak konsisten, pencocokan tetap dilakukan sebisa mungkin (best-effort).
- Effective per data ini: 13 Jul 2026.

AUDIT (temuan & fix, lihat _merge_tiers() untuk detail):
- Data sumber ternyata memecah Parcel vs Freight (kadang Pickup vs Delivery)
  jadi BARIS TERPISAH utk postal range yang sama/tumpang-tindih. Versi lama
  kode ini cuma ambil baris PERTAMA yang cocok -> diam2 kehilangan data tier
  di kolom lain (under-charge sistemik). Ditemukan 7131 pasang range
  tumpang-tindih (7066 US, 58 CN, 7 PH) + 6 entri kota duplikat (SX) --
  SEMUANYA saling melengkapi (0 baris yang benar2 konflik nilai). Sudah
  diperbaiki dengan menggabungkan (merge) semua baris yang cocok, bukan
  ambil yang pertama.
- Data minor lain (belum diperbaiki, dampak kecil): country_code "SX" dipakai
  utk dua nama berbeda ("Saint Martin" & "Sint Marteen") -- Saint Martin
  (sisi Prancis) semestinya ISO "MF", bukan "SX" (Sint Maarten, sisi
  Belanda). Semua baris terkait kebetulan tier-nya sama (B di semua kolom)
  jadi TIDAK mempengaruhi hasil hitung saat ini, tapi nama negara yang
  ditampilkan ke user bisa salah kalau baris pertama yang ke-load kebetulan
  "Sint Marteen" untuk query "Saint Martin" atau sebaliknya. Perlu file
  sumber XLSX asli utk memisahkan dengan benar.
"""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oda_opa_tiers.csv")


class ODAOPAError(Exception):
    pass


def _is_numeric(s):
    return s.isdigit()


class ODAOPALookup:
    def __init__(self, csv_path=CSV_PATH):
        self.csv_path = csv_path
        self.range_index = {}   # country_code -> list of dict(begin,end,is_num,tiers)
        self.city_index = {}    # country_code -> {city_lower: tiers}
        self.country_names = {} # country_code -> display name
        self.name_to_code = {}  # lowercase country name -> country_code
        self._load()

    def _load(self):
        if not os.path.exists(self.csv_path):
            raise ODAOPAError(f"Data file tidak ditemukan: {self.csv_path}")
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cc = row["country_code"].strip().upper()
                name = row["country"].strip()
                if not cc:
                    continue
                self.country_names.setdefault(cc, name)
                self.name_to_code.setdefault(name.lower(), cc)

                tiers = {
                    "parcel_pickup": row["parcel_pickup_tier"].strip() or "No",
                    "freight_pickup": row["freight_pickup_tier"].strip() or "No",
                    "parcel_delivery": row["parcel_delivery_tier"].strip() or "No",
                    "freight_delivery": row["freight_delivery_tier"].strip() or "No",
                }

                begin = row["begin_postal"].strip()
                end = row["end_postal"].strip()
                city = row["city"].strip()

                if begin or end:
                    self.range_index.setdefault(cc, []).append({
                        "begin": begin,
                        "end": end,
                        "is_num": _is_numeric(begin) and _is_numeric(end),
                        "tiers": tiers,
                    })
                elif city:
                    ckey = city.lower()
                    existing = self.city_index.setdefault(cc, {}).get(ckey)
                    if existing is None:
                        self.city_index[cc][ckey] = tiers
                    else:
                        # Duplikat (country, city) -- lihat _merge_tiers(): data
                        # sumber kadang memecah baris Parcel vs Freight utk kota
                        # yang sama. Gabung, jangan overwrite (dulu overwrite ->
                        # baris pertama diam2 hilang).
                        self.city_index[cc][ckey] = self._merge_tiers([existing, tiers])

    # -----------------------------------------------------------------
    def resolve_country_code(self, country):
        key = country.strip()
        if len(key) == 2 and key.upper() in self.country_names:
            return key.upper()
        key_lower = key.lower()
        if key_lower in self.name_to_code:
            return self.name_to_code[key_lower]
        # partial match
        matches = {code for name, code in self.name_to_code.items() if key_lower in name}
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            names = ", ".join(sorted(self.country_names[c] for c in matches))
            raise ODAOPAError(f"'{country}' ambigu, cocok dengan: {names}")
        return None  # negara tidak ada di data ODA/OPA sama sekali

    _TIER_SEVERITY = {"No": 0, "A": 1, "B": 2, "C": 3}

    @classmethod
    def _merge_tiers(cls, tiers_list):
        """
        Gabungkan beberapa dict tiers (masing2 {parcel_pickup, freight_pickup,
        parcel_delivery, freight_delivery}) jadi satu.

        LATAR BELAKANG (temuan audit -- lihat AUDIT_ODA_OPA.md):
        Data sumber (ODA_OPA_tiers_codes.xlsx) ternyata memecah Parcel vs
        Freight (kadang juga Pickup vs Delivery) jadi BARIS TERPISAH untuk
        postal code/range yang SAMA atau tumpang-tindih, dengan kolom yang
        tidak relevan di-default "No". Sebelum fix ini, _match_postal()/
        lookup_by_postal_only() cuma ambil baris PERTAMA yang cocok dan diam2
        BUANG data tier di kolom lain -> under-charge sistemik. Diverifikasi:
        7131 pasang range tumpang-tindih (7066 US, 58 CN, 7 PH) + 6 entri kota
        duplikat (SX), dan SEMUANYA saling melengkapi (0 baris yang benar2
        beda nilai utk kolom yang sama) -> aman digabung apa adanya.

        Kalau suatu saat data diupdate dan MEMANG ada baris yang beda nilai
        utk kolom yang sama (belum pernah terjadi di data saat ini), demi
        keamanan (jangan diam2 under-charge) kita ambil tier yang PALING
        TINGGI severity-nya (No < A < B < C), bukan yang pertama ketemu.
        """
        merged = {"parcel_pickup": "No", "freight_pickup": "No",
                  "parcel_delivery": "No", "freight_delivery": "No"}
        for t in tiers_list:
            for k in merged:
                v = (t.get(k) or "No").strip() or "No"
                if cls._TIER_SEVERITY.get(v, 0) > cls._TIER_SEVERITY.get(merged[k], 0):
                    merged[k] = v
        return merged

    def _match_postal(self, cc, postal_code):
        postal_code = postal_code.strip().upper().replace(" ", "").replace("-", "")
        candidates = self.range_index.get(cc, [])
        if not candidates:
            return None

        numeric_input = _is_numeric(postal_code)
        matched = []
        for c in candidates:
            if c["is_num"] and numeric_input:
                if int(c["begin"]) <= int(postal_code) <= int(c["end"]):
                    matched.append(c["tiers"])
            elif not c["is_num"]:
                b = c["begin"].upper().replace(" ", "")
                e = c["end"].upper().replace(" ", "")
                if b <= postal_code <= e:
                    matched.append(c["tiers"])
        if not matched:
            return None
        if len(matched) == 1:
            return matched[0]
        # >1 range cocok utk postal code ini -> gabung (lihat _merge_tiers).
        return self._merge_tiers(matched)

    def _match_city(self, cc, city):
        cities = self.city_index.get(cc, {})
        return cities.get(city.strip().lower())

    def lookup_by_postal_only(self, postal_code):
        """
        Cari kode pos di SEMUA negara sekaligus (tanpa perlu tahu negaranya dulu).
        Berguna kalau user cuma comot angka kode pos, kayak '334203'.

        Return: list of dict, satu entri per negara yang cocok (bisa lebih dari
        satu kalau kebetulan range-nya tumpang tindih format antar negara).
        Kosong kalau tidak ketemu sama sekali (artinya kemungkinan besar tidak
        ada surcharge ODA/OPA di kode pos itu, di semua negara).
        """
        postal_norm = postal_code.strip().upper().replace(" ", "").replace("-", "")
        numeric_input = _is_numeric(postal_norm)
        matched_by_cc = {}
        for cc, candidates in self.range_index.items():
            hits = []
            for c in candidates:
                if c["is_num"] and numeric_input:
                    if int(c["begin"]) <= int(postal_norm) <= int(c["end"]):
                        hits.append(c["tiers"])
                elif not c["is_num"] and not numeric_input:
                    b = c["begin"].upper().replace(" ", "")
                    e = c["end"].upper().replace(" ", "")
                    if b <= postal_norm <= e:
                        hits.append(c["tiers"])
            if hits:
                matched_by_cc[cc] = hits

        matches = []
        for cc, hits in matched_by_cc.items():
            tiers = hits[0] if len(hits) == 1 else self._merge_tiers(hits)
            matches.append({
                "country": self.country_names.get(cc, cc),
                "country_code": cc,
                "tiers": tiers,
            })
        return matches

    def lookup(self, country, postal_code=None, city=None):
        """
        Return dict:
          {
            "found": bool,
            "match_by": "postal_code" | "city" | "not_found" | "country_not_listed",
            "country": <nama negara resmi di data, kalau ketemu>,
            "tiers": {parcel_pickup, freight_pickup, parcel_delivery, freight_delivery}
          }
        """
        cc = self.resolve_country_code(country)
        if cc is None:
            return {
                "found": False,
                "match_by": "country_not_listed",
                "country": country,
                "tiers": None,
                "note": "Negara ini tidak ada di daftar ODA/OPA -> kemungkinan tidak ada surcharge, "
                        "tapi disarankan konfirmasi ke FedEx.",
            }

        tiers = None
        match_by = "not_found"
        if postal_code:
            tiers = self._match_postal(cc, postal_code)
            if tiers:
                match_by = "postal_code"
        if tiers is None and city:
            tiers = self._match_city(cc, city)
            if tiers:
                match_by = "city"

        return {
            "found": tiers is not None,
            "match_by": match_by,
            "country": self.country_names.get(cc, country),
            "country_code": cc,
            "tiers": tiers,
            "note": None if tiers else (
                "Kode pos/kota tidak ketemu persis di data untuk negara ini -> "
                "kemungkinan area standard (tidak kena ODA/OPA), tapi cek lagi ke FedEx untuk kepastian."
            ),
        }


def format_lookup(result):
    lines = [f"Negara     : {result['country']}"]
    if not result["found"]:
        lines.append(f"Status     : Tidak ditemukan ({result['match_by']})")
        if result.get("note"):
            lines.append(f"Catatan    : {result['note']}")
        return "\n".join(lines)

    t = result["tiers"]
    lines.append(f"Cocok via  : {result['match_by']}")
    lines.append(f"OPA Parcel   (out-of-pickup, kiriman parcel)  : {t['parcel_pickup']}")
    lines.append(f"OPA Freight  (out-of-pickup, kiriman freight) : {t['freight_pickup']}")
    lines.append(f"ODA Parcel   (out-of-delivery, kiriman parcel): {t['parcel_delivery']}")
    lines.append(f"ODA Freight  (out-of-delivery, kiriman freight): {t['freight_delivery']}")
    return "\n".join(lines)


def format_multi_match(matches, postal_code):
    if not matches:
        return (f"Kode pos '{postal_code}' tidak ketemu di negara manapun dalam data -> "
                "kemungkinan tidak ada surcharge ODA/OPA di kode pos ini (di negara manapun "
                "yang formatnya cocok). Tetap disarankan konfirmasi negaranya spesifik ke FedEx.")
    lines = [f"Kode pos '{postal_code}' ketemu di {len(matches)} negara:"]
    for m in matches:
        t = m["tiers"]
        lines.append(
            f"- {m['country']} ({m['country_code']}): "
            f"OPA Parcel={t['parcel_pickup']}, OPA Freight={t['freight_pickup']}, "
            f"ODA Parcel={t['parcel_delivery']}, ODA Freight={t['freight_delivery']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    lk = ODAOPALookup()
    contoh = [
        ("United States", "01002", None),
        ("Japan", "00100", None),
        ("Canada", "X0A0A0", None),
        ("Indonesia", "14510", None),
        ("Albania", None, "Durres"),
        ("Singapore", "123456", None),  # kemungkinan tidak ada di data -> no surcharge
    ]
    for country, postal, city in contoh:
        r = lk.lookup(country, postal_code=postal, city=city)
        print(format_lookup(r))
        print("-" * 60)

    # Contoh: cari kode pos tanpa tahu negaranya
    for kode in ["334203", "01002"]:
        matches = lk.lookup_by_postal_only(kode)
        print(format_multi_match(matches, kode))
        print("-" * 60)
