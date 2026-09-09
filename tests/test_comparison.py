"""
Regression test — comparison/compare.py (lintas carrier & rate_type).
"""
import unittest

from backend.core.schemas import RateRequest
from backend.comparison.compare import compare


class ComparisonTests(unittest.TestCase):

    def _base_request(self, **overrides):
        defaults = dict(carrier="fedex", rate_type="publish", service="IP",
                         direction="export", origin_country="Indonesia",
                         destination_country="Singapore", weight_kg=2.0)
        defaults.update(overrides)
        return RateRequest(**defaults)

    def test_four_way_comparison_all_succeed_for_common_country(self):
        """Singapura punya rate lengkap di ke-4 kombinasi -> tidak boleh ada
        yang masuk daftar 'unavailable'."""
        req = self._base_request()
        result = compare(req, combinations=[("fedex", "publish"), ("fedex", "commercial"),
                                             ("ups", "publish"), ("ups", "commercial")])
        self.assertEqual(len(result.results), 4)
        self.assertEqual(result.unavailable, [])

    def test_cheapest_is_actually_the_minimum_total(self):
        req = self._base_request()
        result = compare(req, combinations=[("fedex", "publish"), ("fedex", "commercial"),
                                             ("ups", "publish"), ("ups", "commercial")])
        totals = [r.total for r in result.results]
        self.assertEqual(result.cheapest.total, min(totals))

    def test_unavailable_country_handled_gracefully_not_crash(self):
        """Vatican City tidak punya rate commercial FedEx -> compare() harus
        tetap jalan (hasil lain tetap dihitung), masuk 'unavailable' dgn
        alasan, bukan exception yang menghentikan seluruh perbandingan."""
        req = self._base_request(destination_country="Vatican City")
        result = compare(req, combinations=[("fedex", "publish"), ("fedex", "commercial")])
        self.assertEqual(len(result.results), 1)  # cuma publish yang berhasil
        self.assertEqual(len(result.unavailable), 1)
        self.assertEqual(result.unavailable[0]["carrier"], "fedex")
        self.assertEqual(result.unavailable[0]["rate_type"], "commercial")

    def test_packages_with_qty_does_not_break_comparison(self):
        """Regression: dulu combo FedEx crash kalau 'packages' diisi dgn
        format qty -> sekarang harus tetap sukses di semua kombinasi."""
        req = self._base_request(
            extra={"packages": [{"qty": 1, "weight_kg": 2.0,
                                  "length_cm": 20, "width_cm": 15, "height_cm": 10}]}
        )
        result = compare(req, combinations=[("fedex", "publish"), ("fedex", "commercial"),
                                             ("ups", "publish"), ("ups", "commercial")])
        self.assertEqual(len(result.results), 4)
        self.assertEqual(result.unavailable, [])


if __name__ == "__main__":
    unittest.main()
