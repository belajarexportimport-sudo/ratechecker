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

    def test_calculate_ups_commercial_named_group_ok(self):
        """API-level regression utk bug named-group override -- pastikan
        fix-nya juga nyampur lewat jalur HTTP, bukan cuma lewat pemanggilan
        Python langsung."""
        res = client.post("/api/rates/calculate", json={
            "carrier": "ups", "rate_type": "commercial", "service": "saver",
            "direction": "export", "origin_country": "Indonesia",
            "destination_country": "Japan", "weight_kg": 2.0,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["base_price"], 550200)

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

    def test_compare_four_way_ok(self):
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
        self.assertEqual(len(data["results"]), 4)
        self.assertEqual(data["unavailable"], [])
        self.assertIsNotNone(data["cheapest"])

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
