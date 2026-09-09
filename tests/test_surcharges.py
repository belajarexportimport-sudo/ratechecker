"""
Test surcharge FedEx yang SEBELUMNYA belum ada test sama sekali: ODA/OPA
lookup dan Special Handling Fees. Base rate & zone sudah ter-cover di
test_fedex.py/test_full_matrix_sweep.py -- file ini isi gap-nya.
"""
import unittest

from backend.carriers.fedex.surcharges.oda_opa import ODAOPALookup
from backend.carriers.fedex.surcharges.special_handling import (
    compute_special_handling,
    ADDRESS_CORRECTION_FEE,
    SATURDAY_PICKUP_FEE,
    SATURDAY_DELIVERY_FEE,
    INBOUND_PROCESSING_FEE,
    ISR_FEE,
)


class ODAOPALookupTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lookup = ODAOPALookup()

    def test_known_city_found(self):
        r = self.lookup.lookup("Albania", city="Berat")
        self.assertTrue(r["found"])
        self.assertEqual(r["match_by"], "city")
        self.assertEqual(r["tiers"]["parcel_pickup"], "B")

    def test_unknown_country_flagged_not_listed(self):
        r = self.lookup.lookup("NegaraFiktifXYZ123")
        self.assertFalse(r["found"])
        self.assertEqual(r["match_by"], "country_not_listed")

    def test_known_country_unmatched_postal_still_found_false_with_note(self):
        """Negara ada di data tapi kode pos/kota tidak match persis -> found
        False TAPI match_by bukan 'country_not_listed' (beda kasus), dan ada
        note yang jelas -- bukan silent None tanpa penjelasan."""
        r = self.lookup.lookup("Albania", postal_code="00000-INVALID")
        self.assertFalse(r["found"])
        self.assertNotEqual(r["match_by"], "country_not_listed")
        self.assertIsNotNone(r["note"])


class SpecialHandlingTests(unittest.TestCase):

    def test_no_flags_no_charges(self):
        result = compute_special_handling(
            service="IP", direction="export", country="Singapore",
            billed_weight_kg=2.0,
        )
        self.assertEqual(result["total_charge"], 0)

    def test_address_correction_flat_fee(self):
        result = compute_special_handling(
            service="IP", direction="export", country="Singapore",
            billed_weight_kg=2.0, address_correction=True,
        )
        self.assertEqual(result["total_charge"], ADDRESS_CORRECTION_FEE)

    def test_saturday_pickup_and_delivery_stack(self):
        result = compute_special_handling(
            service="IP", direction="export", country="Singapore",
            billed_weight_kg=2.0, saturday_pickup=True, saturday_delivery=True,
        )
        self.assertEqual(result["total_charge"], SATURDAY_PICKUP_FEE + SATURDAY_DELIVERY_FEE)

    def test_isr_not_applicable_for_freight_service(self):
        """ISR/DSR/ASR cuma berlaku IP/IE, bukan IPF/IEF -> harus di-skip
        dgn note, BUKAN tetap kena charge diam-diam."""
        result_ip = compute_special_handling(
            service="IP", direction="export", country="Singapore",
            billed_weight_kg=2.0, isr=True,
        )
        result_ipf = compute_special_handling(
            service="IPF", direction="export", country="Singapore",
            billed_weight_kg=100.0, isr=True,
        )
        self.assertEqual(result_ip["total_charge"], ISR_FEE)
        self.assertEqual(result_ipf["total_charge"], 0)
        self.assertTrue(any("freight" in n.lower() for n in result_ipf["notes"]))

    def test_inbound_processing_fee_auto_detected_for_us(self):
        """Inbound Processing Fee auto-detect utk tujuan US/EU tanpa perlu
        flag manual."""
        result = compute_special_handling(
            service="IP", direction="export", country="United States",
            billed_weight_kg=2.0,
        )
        self.assertEqual(result["total_charge"], INBOUND_PROCESSING_FEE)

    def test_inbound_processing_fee_not_applied_outside_us_eu(self):
        result = compute_special_handling(
            service="IP", direction="export", country="Singapore",
            billed_weight_kg=2.0,
        )
        self.assertEqual(result["total_charge"], 0)

    def test_inbound_processing_override_forces_off(self):
        """Override manual False harus menang di atas auto-detect, walau
        tujuannya US."""
        result = compute_special_handling(
            service="IP", direction="export", country="United States",
            billed_weight_kg=2.0, inbound_processing_fee_override=False,
        )
        self.assertEqual(result["total_charge"], 0)


if __name__ == "__main__":
    unittest.main()
