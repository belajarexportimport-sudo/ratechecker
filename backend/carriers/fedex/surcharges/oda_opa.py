"""
FedEx ODA / OPA Tier Lookup - Tahap 1
======================================
Cari tahu apakah suatu kota/kode pos kena:
- Out-of-Pickup-Area Surcharge (OPA)   -> berlaku saat PENJEMPUTAN
- Out-of-Delivery-Area Surcharge (ODA) -> berlaku saat PENGIRIMAN/DELIVERY
Masing-masing dipecah lagi jadi Parcel Services & Freight Services.

Sumber data: ODA_OPA_tiers_codes.xlsx (114 negara, ~67.600 baris kode pos/kota).
Data mentah sudah diekstrak jadi 'oda_opa_tiers.csv' (satu folder dengan file ini)
supaya loading cepat & tidak butuh openpyxl saat runtime.

CATATAN PENTING:
- File ini CUMA kasih tahu TIER (No / Tier A / Tier B / Tier C), BUKAN nominal
  surcharge dalam Rupiah/USD. Nominal per tier ada di tabel surcharge terpisah
  (biasanya di "Surcharge and Other Information" - PDF yang beda dari yang
  sudah di-upload). Kalau ada tabelnya, kasih ke saya, nanti saya gabungkan.
- Kalau negara/kode pos TIDAK ada di data -> kemungkinan besar TIDAK kena
  surcharge ODA/OPA (arealnya dianggap standard), tapi tetap disarankan
  konfirmasi ke FedEx untuk kepastian.
- Sebagian kode pos di sumber asli berupa angka dengan leading zero (misal US
  zip "01002"), itu sudah coba ditangani. Untuk negara dengan format campuran/
  tidak konsisten, pencocokan tetap dilakukan sebisa mungkin (best-effort).
- Effective per data ini: 13 Jul 2026.
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
                    self.city_index.setdefault(cc, {})[city.lower()] = tiers

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

    def _match_postal(self, cc, postal_code):
        postal_code = postal_code.strip().upper().replace(" ", "").replace("-", "")
        candidates = self.range_index.get(cc, [])
        if not candidates:
            return None

        numeric_input = _is_numeric(postal_code)
        for c in candidates:
            if c["is_num"] and numeric_input:
                if int(c["begin"]) <= int(postal_code) <= int(c["end"]):
                    return c["tiers"]
            elif not c["is_num"]:
                b = c["begin"].upper().replace(" ", "")
                e = c["end"].upper().replace(" ", "")
                if b <= postal_code <= e:
                    return c["tiers"]
        return None

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
        matches = []
        for cc, candidates in self.range_index.items():
            for c in candidates:
                if c["is_num"] and numeric_input:
                    if int(c["begin"]) <= int(postal_norm) <= int(c["end"]):
                        matches.append({
                            "country": self.country_names.get(cc, cc),
                            "country_code": cc,
                            "tiers": c["tiers"],
                        })
                        break  # 1 match per negara cukup
                elif not c["is_num"] and not numeric_input:
                    b = c["begin"].upper().replace(" ", "")
                    e = c["end"].upper().replace(" ", "")
                    if b <= postal_norm <= e:
                        matches.append({
                            "country": self.country_names.get(cc, cc),
                            "country_code": cc,
                            "tiers": c["tiers"],
                        })
                        break
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
