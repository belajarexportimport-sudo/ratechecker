"""
Test surcharge FedEx yang SEBELUMNYA belum ada test sama sekali: ODA/OPA
lookup dan Special Handling Fees. Base rate & zone sudah ter-cover di
test_fedex.py/test_full_matrix_sweep.py -- file ini isi gap-nya.
"""
import os
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


class ODAOPADataIntegrityTests(unittest.TestCase):
    """Regresi utk temuan AUDIT_ODA_OPA.md -- ngecek CSV data mentah, bukan
    lewat class ODAOPALookup, supaya kalau file datanya di-update lagi
    (postal code baru / negara baru), penyimpangan dari yang sudah
    diverifikasi ketahuan otomatis, bukan cuma pas ada yang baca ulang
    manual."""

    @classmethod
    def setUpClass(cls):
        import csv
        cls.tier_cols = ["parcel_pickup_tier", "freight_pickup_tier",
                          "parcel_delivery_tier", "freight_delivery_tier"]
        with open(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "backend", "carriers", "fedex", "surcharges", "oda_opa_tiers.csv",
            ),
            newline="", encoding="utf-8",
        ) as f:
            cls.rows = list(csv.DictReader(f))

    def test_all_tier_values_valid(self):
        valid = {"No", "A", "B", "C", ""}
        bad = [
            (r["country"], r["city"], c, r[c])
            for r in self.rows for c in self.tier_cols
            if r[c].strip() not in valid
        ]
        self.assertEqual(bad, [], f"Nilai tier di luar No/A/B/C ditemukan: {bad[:5]}")

    def test_no_range_has_begin_greater_than_end(self):
        bad = []
        for r in self.rows:
            b, e = r["begin_postal"].strip(), r["end_postal"].strip()
            if b and e:
                if b.isdigit() and e.isdigit():
                    if int(b) > int(e):
                        bad.append((r["country"], b, e))
                elif b.upper() > e.upper():
                    bad.append((r["country"], b, e))
        self.assertEqual(bad, [], f"Range dgn begin>end ditemukan: {bad[:5]}")

    def test_overlapping_numeric_ranges_never_conflict_in_value(self):
        """7131 pasang overlap (US/CN/PH) itu SUDAH DIKETAHUI & aman
        (saling melengkapi kolom, bukan beda nilai). Test ini gagal kalau
        update data nanti bikin overlap baru yang punya 2 nilai BEDA di
        kolom tier yang sama (kasus yang butuh keputusan severity-max,
        bukan cuma merge kolom kosong)."""
        by_country = {}
        for r in self.rows:
            b, e = r["begin_postal"].strip(), r["end_postal"].strip()
            if b and e and b.isdigit() and e.isdigit():
                by_country.setdefault(r["country_code"].strip().upper(), []).append(
                    (int(b), int(e), r)
                )
        conflicts = []
        for cc, items in by_country.items():
            items.sort(key=lambda x: x[0])
            active = []
            for b, e, r in items:
                active = [a for a in active if a[1] >= b]
                for ab, ae, ar in active:
                    for c in self.tier_cols:
                        v1 = r[c].strip() or "No"
                        v2 = ar[c].strip() or "No"
                        if v1 != "No" and v2 != "No" and v1 != v2:
                            conflicts.append((cc, c, v1, v2))
                active.append((b, e, r))
        self.assertEqual(conflicts, [], f"Overlap dgn nilai konflik: {conflicts[:5]}")

    def test_alpha_ranges_ca_gb_never_overlap(self):
        """Belum pernah dicek sebelumnya (docstring kode cuma bahas overlap
        numerik) -- CA & GB pakai range huruf. Kalau ini pecah nanti, artinya
        ada risiko _merge_tiers dipanggil dgn kasus yg belum teruji utk
        format alfabet."""
        by_country = {}
        for r in self.rows:
            b, e = r["begin_postal"].strip(), r["end_postal"].strip()
            if b and e and not (b.isdigit() and e.isdigit()):
                cc = r["country_code"].strip().upper()
                by_country.setdefault(cc, []).append(
                    (b.upper().replace(" ", ""), e.upper().replace(" ", ""))
                )
        overlaps = []
        for cc, items in by_country.items():
            for i in range(len(items)):
                b1, e1 = items[i]
                for j in range(i + 1, len(items)):
                    b2, e2 = items[j]
                    if b1 <= e2 and b2 <= e1:
                        overlaps.append((cc, items[i], items[j]))
        self.assertEqual(overlaps, [], f"Overlap alfabet baru ditemukan: {overlaps[:5]}")

    def test_sx_country_code_rows_all_share_same_tier(self):
        """SX dipakai utk 2 nama negara (Saint Martin & Sint Marteen) --
        known limitation krn butuh XLSX asli utk dipisah. Test ini menjaga
        asumsi yg bikin limitation itu 'aman utk sekarang': semua baris SX
        harus tier IDENTIK, supaya nama negara yg salah tampil TIDAK
        menyebabkan nominal surcharge yg salah. Kalau ini gagal, limitation-
        nya naik level jadi bug aktif dan perlu ditangani sungguhan."""
        sx_tiers = set(
            tuple(r[c].strip() or "No" for c in self.tier_cols)
            for r in self.rows if r["country_code"].strip().upper() == "SX"
        )
        self.assertEqual(
            len(sx_tiers), 1,
            f"Baris SX punya tier berbeda-beda ({sx_tiers}) -- nama negara yg "
            "salah tampil sekarang BISA menyebabkan nominal salah juga.",
        )


if __name__ == "__main__":
    unittest.main()
