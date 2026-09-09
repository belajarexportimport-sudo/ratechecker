"""
Full-matrix smoke sweep — beda dari test_fedex.py/test_ups.py (yang cuma
spot-check beberapa negara), test ini iterasi SEMUA negara x semua service x
semua direction x semua rate_type, buat nangkep celah data/zone yang cuma
muncul di kombinasi tertentu (persis pola yang nemuin bug named-group UPS
kemarin -- spot-check ke Singapura tidak akan pernah nemuin bug yang cuma
muncul di Jepang/China).

Prinsip: exception yang termasuk RateEngineError (mis. 'service tidak
tersedia utk negara ini') itu WAJAR & DIHARAPKAN (bukan semua negara punya
semua service) -- yang TIDAK boleh muncul adalah exception LAIN (KeyError,
TypeError, ZeroDivisionError, dll), yang nunjukin ada data hilang atau bug
struktural yang belum ketemu.
"""
import unittest

from backend.core.schemas import RateRequest
from backend.pricing.router import calculate
from backend.core.errors import RateEngineError


def _sweep(carrier, rate_type, direction, countries, services, weight_by_service):
    """Return (success_count, expected_error_count, list-of-unexpected-errors)."""
    unexpected = []
    success = 0
    expected_err = 0
    for country in countries:
        for svc in services:
            kwargs = dict(carrier=carrier, rate_type=rate_type, service=svc,
                           direction=direction, weight_kg=weight_by_service[svc])
            if direction == "export":
                kwargs["origin_country"] = "Indonesia"
                kwargs["destination_country"] = country
            else:
                kwargs["origin_country"] = country
                kwargs["destination_country"] = "Indonesia"
            req = RateRequest(**kwargs)
            try:
                calculate(req)
                success += 1
            except RateEngineError:
                expected_err += 1
            except Exception as e:  # noqa: BLE001 -- sengaja tangkap semua utk sweep
                unexpected.append((country, svc, type(e).__name__, str(e)))
    return success, expected_err, unexpected


class FedExFullMatrixSweepTests(unittest.TestCase):
    SERVICES = ["IP", "IE", "IPF", "IEF"]
    WEIGHT = {"IP": 2.0, "IE": 2.0, "IPF": 100.0, "IEF": 100.0}

    @classmethod
    def setUpClass(cls):
        from backend.carriers.fedex import zones as fz
        cls.promo_countries = sorted(set(v["display_name"] for v in fz.ZONE_INDEX.values()))
        cls.comm_export_countries = sorted(set(
            v["display_name"] for v in fz.COMMERCIAL_ZONE_INDEX["export"].values()))
        cls.comm_import_countries = sorted(set(
            v["display_name"] for v in fz.COMMERCIAL_ZONE_INDEX["import"].values()))

    def test_publish_export_no_unexpected_errors(self):
        s, e, u = _sweep("fedex", "publish", "export", self.promo_countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 800)  # sanity: sweep-nya beneran jalan, bukan kosong

    def test_publish_import_no_unexpected_errors(self):
        s, e, u = _sweep("fedex", "publish", "import", self.promo_countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 800)

    def test_commercial_export_no_unexpected_errors(self):
        s, e, u = _sweep("fedex", "commercial", "export", self.comm_export_countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 500)

    def test_commercial_import_no_unexpected_errors(self):
        s, e, u = _sweep("fedex", "commercial", "import", self.comm_import_countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 500)


class UPSFullMatrixSweepTests(unittest.TestCase):
    SERVICES = ["saver", "expedited", "wwef", "envelope"]
    WEIGHT = {"saver": 2.0, "expedited": 2.0, "wwef": 100.0, "envelope": 0.5}

    @classmethod
    def setUpClass(cls):
        from backend.carriers.ups import zones as uz
        cls.countries = sorted(uz.ZONE_INDEX.keys())

    def test_publish_export_no_unexpected_errors(self):
        s, e, u = _sweep("ups", "publish", "export", self.countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 500)

    def test_publish_import_no_unexpected_errors(self):
        s, e, u = _sweep("ups", "publish", "import", self.countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 400)

    def test_commercial_export_no_unexpected_errors(self):
        s, e, u = _sweep("ups", "commercial", "export", self.countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 500)

    def test_commercial_import_no_unexpected_errors(self):
        s, e, u = _sweep("ups", "commercial", "import", self.countries,
                          self.SERVICES, self.WEIGHT)
        self.assertEqual(u, [])
        self.assertGreater(s, 400)


if __name__ == "__main__":
    unittest.main()
