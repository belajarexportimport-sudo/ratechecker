"""
Regression test — api/routes.py, lewat FastAPI TestClient (tidak perlu
`python run.py` jalan beneran; TestClient panggil ASGI app in-process).
"""
import unittest

from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


class ApiRootTests(unittest.TestCase):

    def test_root_ok(self):
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("message", res.json())


class ApiCalculateTests(unittest.TestCase):

    def test_calculate_fedex_publish_ok(self):
        res = client.post("/api/rates/calculate", json={
            "carrier": "fedex", "rate_type": "publish", "service": "IP",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Singapore", "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["base_price"], 1256000)
        self.assertEqual(data["zone"], "A")

    def test_calculate_ups_commercial_b26_named_group_ok(self):
        """API-level regression utk bug named-group override -- pastikan
        fix-nya juga nyampur lewat jalur HTTP, bukan cuma lewat pemanggilan
        Python langsung. Tier eksplisit b26 (bukan lagi 'commercial'
        generik -- lihat AUDIT_UPS_COMMERCIAL.md, B26 tidak lagi default
        diam-diam)."""
        res = client.post("/api/rates/calculate", json={
            "carrier": "ups", "rate_type": "b26", "service": "saver",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Japan", "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["base_price"], 550200)

    def test_calculate_ups_commercial_a26_named_group_ok(self):
        """A26 HARUS bisa diakses langsung lewat HTTP juga -- tidak
        tersembunyi di belakang default B26."""
        res = client.post("/api/rates/calculate", json={
            "carrier": "ups", "rate_type": "a26", "service": "saver",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Japan", "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["base_price"], 629400)

    def test_calculate_ups_commercial_generic_without_tier_returns_400(self):
        """rate_type='commercial' generik tanpa tier eksplisit sekarang
        harus 400 (UPSRateError -> RateEngineError), bukan diam-diam 200
        dgn B26."""
        res = client.post("/api/rates/calculate", json={
            "carrier": "ups", "rate_type": "commercial", "service": "saver",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Japan", "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 400)

    def test_calculate_fedex_commercial_markup_ok(self):
        """extra['markup_pct'] FedEx commercial nyampur lewat HTTP juga."""
        res = client.post("/api/rates/calculate", json={
            "carrier": "fedex", "rate_type": "commercial", "service": "IP",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Singapore", "weight_kg": 2.0,
            "extra": {"markup_pct": 20},
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["base_price"], 324676)
        self.assertIn("Markup Commercial (20%)", data["surcharges"])
        self.assertGreater(data["total"], data["base_price"])

    def test_calculate_fedex_commercial_markup_invalid_pct_returns_400(self):
        res = client.post("/api/rates/calculate", json={
            "carrier": "fedex", "rate_type": "commercial", "service": "IP",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Singapore", "weight_kg": 2.0,
            "extra": {"markup_pct": 10},
        })
        self.assertEqual(res.status_code, 400)

    def test_calculate_missing_required_field_returns_422(self):
        res = client.post("/api/rates/calculate", json={
            "carrier": "fedex", "service": "IP", "direction": "export",
            "origin_country": "Indonesia",
            # destination_country sengaja dihilangkan
            "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 422)

    def test_calculate_unavailable_country_returns_4xx_not_500(self):
        res = client.post("/api/rates/calculate", json={
            "carrier": "fedex", "rate_type": "commercial", "service": "IP",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Vatican City", "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 400)

    def test_calculate_packages_with_qty_does_not_500(self):
        """Regression HTTP-level utk bug packages/qty yang sudah diperbaiki."""
        res = client.post("/api/rates/calculate", json={
            "carrier": "fedex", "rate_type": "publish", "service": "IP",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Singapore", "weight_kg": 2.0,
            "packages": [{"qty": 1, "weight_kg": 2.0, "length_cm": 20,
                          "width_cm": 15, "height_cm": 10}],
        })
        self.assertEqual(res.status_code, 200)


class ApiCompareTests(unittest.TestCase):

    def test_compare_five_way_ok(self):
        """5 hasil (bukan 4): combo ["ups","commercial"] generik di-expand
        jadi 2 baris (A26 & B26) oleh compare() -- lihat
        AUDIT_UPS_COMMERCIAL.md, B26 tidak lagi default diam-diam."""
        res = client.post("/api/rates/compare", json={
            "base_request": {
                "carrier": "fedex", "rate_type": "publish", "service": "IP",
                "direction": "export", "origin_country": "Indonesia",
                "destination_country": "Singapore", "weight_kg": 2.0,
            },
            "combinations": [["fedex", "publish"], ["fedex", "commercial"],
                              ["ups", "publish"], ["ups", "commercial"]],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["results"]), 5)
        self.assertEqual(data["unavailable"], [])
        self.assertIsNotNone(data["cheapest"])

    def test_compare_ups_commercial_explicit_tier_via_3element_combo(self):
        """combinations mendukung elemen ke-3 (dict extra) utk override
        tier eksplisit -- combo TIDAK di-expand kalau tier sudah eksplisit."""
        res = client.post("/api/rates/compare", json={
            "base_request": {
                "carrier": "fedex", "rate_type": "publish", "service": "IP",
                "direction": "export", "origin_country": "Indonesia",
                "destination_country": "Singapore", "weight_kg": 2.0,
            },
            "combinations": [["ups", "commercial", {"ups_tier": "a26"}]],
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["unavailable"], [])

    def test_compare_missing_base_request_returns_422(self):
        res = client.post("/api/rates/compare", json={
            "combinations": [["fedex", "publish"]],
        })
        self.assertEqual(res.status_code, 422)

    def test_compare_bad_combinations_shape_returns_422(self):
        res = client.post("/api/rates/compare", json={
            "base_request": {
                "carrier": "fedex", "rate_type": "publish", "service": "IP",
                "direction": "export", "origin_country": "Indonesia",
                "destination_country": "Singapore", "weight_kg": 2.0,
            },
            "combinations": ["fedex-publish"],  # harus list-of-2-elemen, bukan string
        })
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
