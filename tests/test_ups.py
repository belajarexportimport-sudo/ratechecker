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


class UPSDimensionsCmFallbackTests(unittest.TestCase):
    """Regression utk bug yang sudah diperbaiki: request.dimensions_cm tanpa
    'packages' eksplisit (skenario paling umum -- persis yang dikirim
    index.html trial UI) SEBELUMNYA cuma dipakai utk hitung DIM weight, tapi
    AHS/LPS/OMX SAMA SEKALI TIDAK DICEK walau datanya sudah ada."""

    def test_oversized_dimension_triggers_ahs_without_explicit_packages(self):
        req = RateRequest(carrier="ups", rate_type="publish", service="saver",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=5.0,
                           dimensions_cm=(150, 30, 30))  # L>122cm -> AHS
        r = calculate(req)
        ahs_keys = [k for k in r.surcharges if "AHS" in k]
        self.assertTrue(ahs_keys, f"AHS tidak terdeteksi, surcharges: {r.surcharges}")

    def test_large_dimension_picks_dim_weight_over_actual(self):
        """max(actual, dim) -- dim weight (12kg) > actual (1kg) -> chargeable
        weight yg dipakai harus dim weight, bukan actual."""
        req = RateRequest(carrier="ups", rate_type="publish", service="saver",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=1.0,
                           dimensions_cm=(50, 40, 30))
        r = calculate(req)
        self.assertEqual(r.extra["pkg_details"][0]["chargeable_kg"], 12.0)
        self.assertEqual(r.extra["pkg_details"][0]["dim_kg"], 12.0)

    def test_small_dimension_picks_actual_over_dim_weight(self):
        req = RateRequest(carrier="ups", rate_type="publish", service="saver",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=5.0,
                           dimensions_cm=(20, 15, 10))
        r = calculate(req)
        self.assertEqual(r.extra["pkg_details"][0]["chargeable_kg"], 5.0)

    def test_no_dimensions_behaves_exactly_as_before(self):
        req = RateRequest(carrier="ups", rate_type="publish", service="saver",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0)
        r = calculate(req)
        self.assertEqual(r.base_price, 1789024)
        ahs_keys = [k for k in r.surcharges if "AHS" in k]
        self.assertEqual(ahs_keys, [])


class UPSPackageSurchargeUnitTests(unittest.TestCase):
    """Unit test langsung ke evaluate_package() utk AHS/LPS/OMX/WWEF --
    lebih presisi dari test lewat calculate() krn bisa cek reasons & floor
    weight per kondisi spesifik satu-satu."""

    @classmethod
    def setUpClass(cls):
        from backend.carriers.ups.rules import evaluate_package
        cls.evaluate_package = staticmethod(evaluate_package)

    def test_lps_triggered_by_girth_over_300_under_omx_threshold(self):
        """total_dim (L+girth) 301-400cm, L<=274cm, weight<=70kg -> LPS
        (bukan OMX)."""
        pr = self.evaluate_package(weight_kg=30, length_cm=150, width_cm=60, height_cm=60)
        # girth = 2*60+2*60=240; total_dim=150+240=390 (LPS range: >300, <=400 & L<=274)
        self.assertEqual(pr.surcharge_type, "LPS")
        self.assertGreaterEqual(pr.chargeable_weight, 40.0)  # LPS floor 40kg

    def test_omx_triggered_by_length_over_274(self):
        pr = self.evaluate_package(weight_kg=30, length_cm=280, width_cm=40, height_cm=40)
        self.assertEqual(pr.surcharge_type, "OMX")

    def test_omx_triggered_by_weight_over_70(self):
        pr = self.evaluate_package(weight_kg=75, length_cm=50, width_cm=40, height_cm=40)
        self.assertEqual(pr.surcharge_type, "OMX")

    def test_omx_triggered_by_total_dim_over_400(self):
        pr = self.evaluate_package(weight_kg=30, length_cm=200, width_cm=60, height_cm=60)
        # girth=240, total_dim=440 -> OMX (total_dim>400)
        self.assertEqual(pr.surcharge_type, "OMX")

    def test_normal_package_no_surcharge(self):
        pr = self.evaluate_package(weight_kg=5, length_cm=30, width_cm=20, height_cm=15)
        self.assertEqual(pr.surcharge_type, "")
        self.assertEqual(pr.surcharge_cost, 0)

    def test_wwef_waives_ahs_lps_omx_but_floors_71kg(self):
        """WWEF: AHS/LPS/OMX diwaive TOTAL, tapi minimum 71kg per package
        tetap berlaku. Dimensi dipilih kecil (dim_weight < 71kg) supaya
        yang diuji murni floor 71kg-nya, bukan kebetulan dim_weight lebih
        besar dari itu."""
        pr = self.evaluate_package(weight_kg=30, length_cm=280, width_cm=20, height_cm=20,
                                    is_wwef=True)
        self.assertEqual(pr.surcharge_type, "")
        self.assertEqual(pr.surcharge_cost, 0)
        self.assertEqual(pr.chargeable_weight, 71.0)


if __name__ == "__main__":
    unittest.main()
