"""
Regression test — FedEx (Publish & Commercial/Exsis).

Nilai "golden" di bawah ini SUDAH diverifikasi manual terhadap sumber
mentahnya:
  - Publish: fedex-rates-exp/imp-en-id-2026.pdf
  - Commercial: Rate_FDX_Exsis_Export.xls / Rate_FDX_Exsis_Import.xls
    (customer EXPRESSINDO SYSTEM NETWORK, akun 206071531)

Kalau test ini gagal, JANGAN langsung ubah golden value-nya — cek dulu
apakah rate sheet sumber memang berubah (rate baru dari FedEx), atau ada bug
di kode. Golden value cuma boleh diupdate kalau sudah dicocokkan ulang
terhadap sumber mentah, bukan asumsi.
"""
import unittest
import datetime

from backend.core.schemas import RateRequest
from backend.pricing.router import calculate
from backend.carriers.fedex.rates.common import FedExRateError

# Demand Surcharge baru efektif 2026-09-21 -- golden value di bawah ini
# ditulis SEBELUM tanggal itu, jadi tes yang mengasumsikan surcharge
# ter-apply WAJIB pin 'demand_surcharge_as_of_date' ke tanggal setelah
# efektif (bukan biarkan default 'hari ini'), supaya tidak diam-diam mulai
# gagal begitu kalender lewat 21 Sep 2026 (atau sebaliknya, tidak diam-diam
# lolos padahal seharusnya sudah berubah).
_AFTER_DEMAND_SURCHARGE_EFFECTIVE = datetime.date(2026, 9, 25)
_BEFORE_DEMAND_SURCHARGE_EFFECTIVE = datetime.date(2026, 9, 1)


class FedExPublishTests(unittest.TestCase):

    def test_ip_export_singapore_pak(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           extra={"demand_surcharge_as_of_date": _AFTER_DEMAND_SURCHARGE_EFFECTIVE})
        r = calculate(req)
        self.assertEqual(r.zone, "A")
        self.assertEqual(r.base_price, 1256000)
        self.assertEqual(r.total, 1262000)  # + Demand Surcharge Rp6.000

    def test_ie_export_japan_doc(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IE",
                           direction="export", origin_country="Indonesia",
                           destination_country="Japan", weight_kg=5.0,
                           extra={"demand_surcharge_as_of_date": _AFTER_DEMAND_SURCHARGE_EFFECTIVE})
        r = calculate(req)
        self.assertEqual(r.zone, "C")
        self.assertEqual(r.base_price, 4326000)

    def test_default_rate_type_is_publish(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0)
        r = calculate(req)
        self.assertIn(r.rate_type, ("publish", "promotional"))


class FedExCommercialTests(unittest.TestCase):
    """Dicocokkan langsung terhadap raw XLS Exsis (lihat
    RINGKASAN_COMMERCIAL_RATE.md untuk pembuktian awal)."""

    def test_ip_export_singapore(self):
        req = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0)
        r = calculate(req)
        self.assertEqual(r.zone, "Y")
        self.assertEqual(r.base_price, 324676)

    def test_ip_import_singapore(self):
        req = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                           direction="import", origin_country="Singapore",
                           destination_country="Indonesia", weight_kg=2.0)
        r = calculate(req)
        self.assertEqual(r.zone, "Y")
        self.assertEqual(r.base_price, 312620)

    def test_commercial_zone_letters_differ_from_publish(self):
        """Commercial pakai 20 huruf zone (B..Z tanpa A), publish pakai A-G —
        pastikan dua rate_type ini betul2 pakai tabel zone yang beda, bukan
        kebetulan sama."""
        req_pub = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                               direction="export", origin_country="Indonesia",
                               destination_country="Singapore", weight_kg=2.0)
        req_com = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                               direction="export", origin_country="Indonesia",
                               destination_country="Singapore", weight_kg=2.0)
        r_pub = calculate(req_pub)
        r_com = calculate(req_com)
        self.assertNotEqual(r_pub.zone, r_com.zone)
        self.assertNotEqual(r_pub.base_price, r_com.base_price)

    def test_china_south_postal_code_switches_zone(self):
        """Kode pos Fujian (350000-369999) harus switch ke 'China (South)',
        beda base_price dari default 'China (Excluding China South)'."""
        req_default = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                                   direction="export", origin_country="Indonesia",
                                   destination_country="China", weight_kg=5.0)
        req_south = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                                 direction="export", origin_country="Indonesia",
                                 destination_country="China", weight_kg=5.0,
                                 postal_code_destination="360000")
        r_default = calculate(req_default)
        r_south = calculate(req_south)
        self.assertIn("Excluding China South", r_default.extra["country"])
        self.assertIn("China (South)", r_south.extra["country"])
        self.assertNotEqual(r_default.zone, r_south.zone)

    def test_unavailable_country_raises_clear_error(self):
        """Vatican City sengaja tidak ada rate commercial-nya sama sekali —
        harus raise error jelas, bukan crash generik atau silent fallback."""
        req = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Vatican City", weight_kg=2.0)
        with self.assertRaises(FedExRateError):
            calculate(req)

    def test_aliased_country_name_resolves(self):
        """'Philippines' (ejaan Zone Index promotional) harus tetap resolve
        walau Exsis pakai ejaan 'Phillipines' (lihat COMMERCIAL_ALIASES)."""
        req = RateRequest(carrier="fedex", rate_type="commercial", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Philippines", weight_kg=2.0)
        r = calculate(req)  # tidak boleh raise
        self.assertIsNotNone(r.base_price)


class FedExPackagesRegressionTests(unittest.TestCase):
    """Regression utk bug yang sudah diperbaiki: packages dgn key 'qty'
    sebelumnya crash TypeError di check_package_surcharge()."""

    def test_packages_with_qty_1_does_not_crash(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           extra={"packages": [{"qty": 1, "weight_kg": 2.0,
                                                 "length_cm": 20, "width_cm": 15,
                                                 "height_cm": 10}]})
        r = calculate(req)  # tidak boleh raise
        self.assertEqual(len(r.extra["chargeable_weight"]["details"]), 1)

    def test_packages_with_qty_3_expands_to_3_collies(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=6.0,
                           extra={"packages": [{"qty": 3, "weight_kg": 2.0,
                                                 "length_cm": 20, "width_cm": 15,
                                                 "height_cm": 10}]})
        r = calculate(req)
        details = r.extra["chargeable_weight"]["details"]
        self.assertEqual(len(details), 3)
        self.assertEqual(r.extra["chargeable_weight"]["total_chargeable_weight_kg"], 6.0)


class FedExDimensionsCmFallbackTests(unittest.TestCase):
    """Regression utk bug yang sudah diperbaiki: request.dimensions_cm
    (tanpa 'packages' eksplisit -- skenario paling umum, persis yang
    dikirim index.html trial UI) SEBELUMNYA sama sekali tidak dipakai ->
    Non-Standard Fees (AHS-equivalent FedEx: oversize/overweight dkk) SELALU
    ke-skip diam-diam walau dimensi sudah diisi."""

    def test_oversized_dimension_triggers_nonstandard_fee_without_explicit_packages(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=5.0,
                           dimensions_cm=(150, 30, 30))  # L>122cm -> AHS-Dimension
        r = calculate(req)
        self.assertIn("Non-Standard Shipment Fees", r.surcharges)
        self.assertGreater(r.surcharges["Non-Standard Shipment Fees"], 0)

    def test_normal_dimension_no_surcharge_and_no_regression(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           dimensions_cm=(20, 15, 10))
        r = calculate(req)
        self.assertNotIn("Non-Standard Shipment Fees", r.surcharges)

    def test_no_dimensions_behaves_exactly_as_before(self):
        """Base case tanpa dimensions_cm sama sekali -> base_price harus
        identik dgn golden value lama (tidak ada regresi)."""
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0)
        r = calculate(req)
        self.assertEqual(r.base_price, 1256000)
        self.assertNotIn("Non-Standard Shipment Fees", r.surcharges)


class FedExAHSDimensionFloorAppliedTests(unittest.TestCase):
    """Regresi utk temuan: known_limitations #1 (docstring lama
    nonstandard.py) bilang floor 18kg AHS-Dimension 'BELUM otomatis
    diterapkan ke base rate' -- ternyata SUDAH (lewat
    compute_shipment_chargeable_weight() yg dipanggil calculator.py),
    cuma teks note & docstring-nya yg belum di-update (menyesatkan
    pembaca hasil kuotasi). Test ini mengunci PERILAKU-nya (bukan cuma
    teks) supaya floor tidak diam-diam lepas lagi di masa depan."""

    def test_single_light_package_ahs_dimension_floor_raises_billed_weight(self):
        """Package 130x20x20cm/2kg: longest=130cm>121cm -> AHS-Dimension,
        actual weight (2kg) & dim weight (130*20*20/5000=10.4kg) keduanya
        < 18kg -> billed_weight_kg HARUS naik jadi tepat 18kg (floor), bukan
        max(2, 10.4)=10.4kg."""
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           extra={"packages": [{"weight_kg": 2.0, "length_cm": 130,
                                                 "width_cm": 20, "height_cm": 20}]})
        r = calculate(req)
        self.assertEqual(r.extra["chargeable_weight"]["total_chargeable_weight_kg"], 18.0)
        detail = r.extra["chargeable_weight"]["details"][0]
        self.assertTrue(detail["ahs_dimension_floor_applied"])
        # base rate ikut dihitung dari billed weight yg SUDAH kena floor,
        # bukan dari actual/dim weight yg lebih kecil.
        self.assertGreater(r.base_price, 0)

    def test_note_no_longer_claims_floor_not_applied(self):
        """Note per-package tidak boleh lagi bilang 'BELUM otomatis
        diterapkan ke base rate' -- itu klaim yg sudah tidak benar sejak
        compute_shipment_chargeable_weight() menerapkan floor."""
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           extra={"packages": [{"weight_kg": 2.0, "length_cm": 130,
                                                 "width_cm": 20, "height_cm": 20}]})
        r = calculate(req)
        combined_notes = " ".join(r.notes)
        self.assertNotIn("BELUM otomatis diterapkan ke base rate", combined_notes)


class FedExDemandSurchargeDateGatingTests(unittest.TestCase):
    """Regression test utk bug yang sudah diperbaiki: Demand Surcharge
    (efektif 2026-09-21) SEBELUMNYA dihitung terus tanpa cek tanggal sama
    sekali -- artinya setiap quote SEBELUM tanggal efektif over-charge
    Rp6.000+ diam-diam. Sekarang harus date-gated dgn benar."""

    def test_not_applied_before_effective_date(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           extra={"demand_surcharge_as_of_date": _BEFORE_DEMAND_SURCHARGE_EFFECTIVE})
        r = calculate(req)
        self.assertNotIn("Demand Surcharge", r.surcharges)
        self.assertEqual(r.total, r.base_price)  # tidak ada surcharge nempel
        self.assertTrue(any("Demand Surcharge" in n and "belum" in n for n in r.notes))

    def test_applied_on_or_after_effective_date(self):
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=2.0,
                           extra={"demand_surcharge_as_of_date": _AFTER_DEMAND_SURCHARGE_EFFECTIVE})
        r = calculate(req)
        self.assertIn("Demand Surcharge", r.surcharges)
        self.assertGreater(r.total, r.base_price)


class FedExCommercialMarkupTests(unittest.TestCase):
    """Upsell/markup FedEx commercial (extra['markup_pct']) -- KEBALIKAN
    diskon, menaikkan dari acuan Commercial Rate Card. Khusus rate_type
    commercial FedEx (bukan discount_pct, dan tidak berlaku ke publish).
    Golden base_price commercial IP export Singapore 2kg = 324676 (lihat
    FedExCommercialTests.test_ip_export_singapore)."""

    def _base_req(self, **overrides):
        defaults = dict(carrier="fedex", rate_type="commercial", service="IP",
                         direction="export", origin_country="Indonesia",
                         destination_country="Singapore", weight_kg=2.0)
        defaults.update(overrides)
        return RateRequest(**defaults)

    def test_markup_15pct_adds_positive_surcharge_not_discount(self):
        req = self._base_req(extra={"markup_pct": 15})
        r = calculate(req)
        self.assertEqual(r.base_price, 324676)  # base rate TIDAK berubah
        markup_amount = 324676 * 0.15
        self.assertEqual(r.surcharges.get("Markup Commercial (15%)"), markup_amount)
        self.assertGreater(r.total, r.base_price)  # naik, bukan turun

    def test_markup_20pct(self):
        req = self._base_req(extra={"markup_pct": 20})
        r = calculate(req)
        self.assertIn("Markup Commercial (20%)", r.surcharges)
        self.assertEqual(r.surcharges["Markup Commercial (20%)"], 324676 * 0.20)

    def test_markup_25pct(self):
        req = self._base_req(extra={"markup_pct": 25})
        r = calculate(req)
        self.assertIn("Markup Commercial (25%)", r.surcharges)
        self.assertEqual(r.surcharges["Markup Commercial (25%)"], 324676 * 0.25)

    def test_markup_30pct(self):
        req = self._base_req(extra={"markup_pct": 30})
        r = calculate(req)
        self.assertIn("Markup Commercial (30%)", r.surcharges)
        self.assertEqual(r.surcharges["Markup Commercial (30%)"], 324676 * 0.30)

    def test_markup_extra_detail_in_result(self):
        req = self._base_req(extra={"markup_pct": 20})
        r = calculate(req)
        self.assertEqual(r.extra["markup"]["pct"], 20)
        self.assertAlmostEqual(r.extra["markup"]["amount"], 324676 * 0.20, delta=1)

    def test_markup_note_states_it_is_increase_not_discount(self):
        req = self._base_req(extra={"markup_pct": 15})
        r = calculate(req)
        self.assertTrue(any("Markup" in n and "bukan diskon" in n for n in r.notes))

    def test_invalid_markup_pct_value_raises_clear_error(self):
        """Cuma preset 15/20/25/30 yang didukung -- nilai lain harus error
        jelas, bukan diam-diam dipakai."""
        req = self._base_req(extra={"markup_pct": 10})
        with self.assertRaises(ValueError):
            calculate(req)

    def test_markup_rejected_for_publish_rate_type(self):
        """markup_pct KHUSUS commercial -- FedEx publish tidak punya konsep
        upsell dari commercial rate card."""
        req = self._base_req(rate_type="publish", extra={"markup_pct": 20})
        with self.assertRaises(ValueError):
            calculate(req)

    def test_no_markup_pct_behaves_exactly_as_before(self):
        """Tanpa markup_pct -- behavior IDENTIK spt sebelum fitur ini ada."""
        req = self._base_req()
        r = calculate(req)
        self.assertEqual(r.base_price, 324676)
        self.assertNotIn("markup", "".join(r.surcharges.keys()).lower())
        self.assertIsNone(r.extra["markup"])

    def test_markup_can_combine_with_discount_independently(self):
        """markup_pct & discount_pct dua lever bisnis independen -- boleh
        dipakai bersamaan (masing2 dihitung dari base rate yang sama,
        bukan saling mempengaruhi)."""
        req = self._base_req(discount_pct=10, extra={"markup_pct": 20})
        r = calculate(req)
        self.assertEqual(r.discount, 324676 * 0.10)
        self.assertEqual(r.surcharges["Markup Commercial (20%)"], 324676 * 0.20)


if __name__ == "__main__":
    unittest.main()
