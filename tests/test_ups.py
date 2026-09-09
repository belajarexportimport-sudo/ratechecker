"""
Regression test — UPS (Publish & Commercial A26/B26).

Golden value publish sudah di-diff PENUH (semua 221 negara, semua 8 tabel
rate, semua zone & weight break -> 0 mismatch) terhadap `ups-calculator`
(referensi production) -- lihat AUDIT_UPS_COMMERCIAL.md.

Golden value commercial (Jepang, China South) khusus dipilih karena
sebelumnya JADI BUKTI bug named-group override (lihat
AUDIT_UPS_COMMERCIAL.md) -- kalau test ini gagal lagi di masa depan,
kemungkinan besar ada regresi di `_get_group_key()` / `A26_B26_GROUPS`.
"""
import unittest

from backend.core.schemas import RateRequest
from backend.pricing.router import calculate
from backend.carriers.ups.zones import ZONE_INDEX
from backend.carriers.ups.rates.commercial import lookup_rate, A26_RATES, _get_group_key


class UPSPublishTests(unittest.TestCase):

    def test_saver_export_singapore(self):
        req = RateRequest(carrier="ups", rate_type="publish", service="saver",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0)
        r = calculate(req)
        self.assertEqual(r.zone, "1")
        self.assertEqual(r.base_price, 1789024)

    def test_full_zone_index_matches_reference_221_countries(self):
        """Sanity check struktural: 221 negara, 6 field per negara (bukan
        angka ajaib -- ini jumlah pasti dari referensi production)."""
        self.assertEqual(len(ZONE_INDEX), 221)
        sample = ZONE_INDEX["japan"]
        for field in ("saverExport", "expeditedExport", "saverImport",
                      "expeditedImport", "wwefExport", "wwefImport"):
            self.assertIn(field, sample)


class UPSCommercialNamedGroupTests(unittest.TestCase):
    """Regression test spesifik utk bug named-group override yang sudah
    diperbaiki -- lihat AUDIT_UPS_COMMERCIAL.md bagian 'BUG DITEMUKAN'."""

    def test_japan_a26_uses_named_group_not_zone_number(self):
        """Jepang zone-3, tapi commercial rate-nya HARUS pakai tabel
        'japan, korea, taiwan', BUKAN tabel zone-3 generik."""
        rate, mode = lookup_rate("export", "saver", 3, 2.0,
                                  rate_type="a26", country="Japan")
        self.assertEqual(rate, 629400)  # named-group value

        zone3_generic = A26_RATES["export"]["saver"][3][2.0]
        self.assertEqual(zone3_generic, 590100)  # nilai zone-3 polos, HARUS beda
        self.assertNotEqual(rate, zone3_generic)

    def test_china_south_a26_uses_named_group(self):
        rate, mode = lookup_rate("export", "saver", 10, 2.0,
                                  rate_type="a26", country="China South")
        self.assertEqual(rate, 629400)

        zone10_generic = A26_RATES["export"]["saver"][10][2.0]
        self.assertEqual(zone10_generic, 532600)
        self.assertNotEqual(rate, zone10_generic)

    def test_country_without_override_uses_zone_number(self):
        """Singapura TIDAK ada di named-group manapun -> harus tetap pakai
        zone angka seperti biasa (fix ini tidak boleh mengubah negara yang
        memang tidak affected)."""
        rate, mode = lookup_rate("export", "saver", 1, 2.0,
                                  rate_type="a26", country="Singapore")
        zone1_generic = A26_RATES["export"]["saver"][1][2.0]
        self.assertEqual(rate, zone1_generic)

    def test_all_221_countries_resolve_consistently(self):
        """Full regression: tiap negara, hasil lookup_rate() harus PERSIS
        sama dgn resolusi manual (group kalau ada override, else zone)."""
        table = A26_RATES["export"]["saver"]
        mismatches = []
        for country_key, zdata in ZONE_INDEX.items():
            zone = zdata.get("saverExport")
            if zone is None:
                continue
            group_key = _get_group_key(country_key, table)
            expected_table = table.get(group_key) if group_key else table.get(zone)
            if expected_table is None:
                continue
            expected_val = expected_table.get(2.0)
            rate, _ = lookup_rate("export", "saver", zone, 2.0,
                                   rate_type="a26", country=country_key)
            if rate != expected_val:
                mismatches.append((country_key, zone, group_key, expected_val, rate))
        self.assertEqual(mismatches, [], f"Mismatch ditemukan: {mismatches}")

    def test_end_to_end_japan_commercial_via_calculate(self):
        """Full pipeline (bukan cuma lookup_rate langsung) -- rate_type
        'commercial' resolve ke B26 (lihat catatan A26 vs B26 default di
        AUDIT_UPS_COMMERCIAL.md -- ini SENGAJA, bukan bug)."""
        req = RateRequest(carrier="ups", rate_type="commercial", service="saver",
                           direction="export", origin_country="Indonesia",
                           destination_country="Japan", weight_kg=2.0)
        r = calculate(req)
        self.assertEqual(r.base_price, 550200)  # B26 'japan, korea, taiwan' @2kg


if __name__ == "__main__":
    unittest.main()
