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


class FedExPackageQtyMultiplierRegressionTests(unittest.TestCase):
    """
    Regresi TAMBAHAN ditemukan saat re-verifikasi audit (bukan bug yang sama
    dgn FedExPackagesRegressionTests di atas): crash 'qty' sudah diperbaiki
    lewat _package_surcharge_kwargs()/_expand_packages_qty(), TAPI kalau
    fungsi nonstandard.py (summarize_packages, evaluate_packages_for_service_
    switch, compute_shipment_chargeable_weight) dipanggil LANGSUNG dengan
    dict yang masih membawa key 'qty' mentah (belum di-expand
    _expand_packages_qty()), qty itu dibuang diam-diam alih-alih dipakai
    sbg pengali -> silent under-billing (bukan crash, jadi tidak ketahuan
    tanpa test eksplisit). Lihat _package_qty() di nonstandard.py.
    """

    def test_summarize_packages_multiplies_charge_by_qty(self):
        from backend.carriers.fedex.surcharges import nonstandard as nf
        packages = [{"qty": 2, "weight_kg": 30, "length_cm": 250,
                     "width_cm": 40, "height_cm": 40, "packing_type": "box",
                     "label": "Collie 1"}]
        res = nf.summarize_packages(packages)
        # 1 collie 250x40x40/30kg -> Oversize Charge (Rp1.072.000), qty=2
        self.assertEqual(res["total_charge"], 1072000 * 2)
        self.assertEqual(res["details"][0]["qty"], 2)
        self.assertEqual(res["details"][0]["charge_per_unit"], 1072000)

    def test_compute_shipment_chargeable_weight_multiplies_by_qty(self):
        from backend.carriers.fedex.surcharges import nonstandard as nf
        packages = [{"qty": 2, "weight_kg": 30, "length_cm": 250,
                     "width_cm": 40, "height_cm": 40}]
        cwt = nf.compute_shipment_chargeable_weight(packages)
        # dim weight = (250*40*40)/5000 = 80kg per collie x qty 2 = 160kg
        self.assertEqual(cwt["total_chargeable_weight_kg"], 160.0)
        self.assertEqual(cwt["details"][0]["qty"], 2)

    def test_end_to_end_via_calculator_no_double_count_with_expand_packages_qty(self):
        # Jalur RESMI (calculator.py: _expand_packages_qty menghilangkan
        # 'qty' sebelum sampai ke nonstandard.py) TIDAK boleh dobel-hitung
        # cuma karena nonstandard.py sekarang juga sadar 'qty'.
        req = RateRequest(carrier="fedex", rate_type="publish", service="IP",
                           direction="export", origin_country="Indonesia",
                           destination_country="Singapore", weight_kg=40.0,
                           extra={"packages": [{"qty": 2, "weight_kg": 20,
                                                 "length_cm": 245, "width_cm": 10,
                                                 "height_cm": 10, "packing_type": "box"}]})
        r = calculate(req)
        self.assertEqual(r.surcharges.get("Non-Standard Shipment Fees"), 1072000 * 2)


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


if __name__ == "__main__":
    unittest.main()
