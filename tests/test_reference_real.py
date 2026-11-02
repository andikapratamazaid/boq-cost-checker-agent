"""Tests against the REAL HSPK excerpt (Perbup Kab. Bengkulu Selatan No. 25/2025, TA 2026)."""
import unittest

from boqcheck.reference import load_reference, validate_reference


class TestRealReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = load_reference()
        cls.findings = validate_reference(cls.ref)

    def test_excerpt_size(self):
        self.assertEqual(len(self.ref.items), 38)
        self.assertEqual(len(self.ref.components), 260)
        self.assertEqual(self.ref.items.item_id.nunique(), 38)

    def test_known_inconsistencies_of_the_source_are_found(self):
        got = {(f.row, f.check) for f in self.findings}
        self.assertIn(("BS03", "HSPK_TOTAL_MISMATCH"), got)        # headline 168,750 vs labor total 191,250
        self.assertIn(("BS14", "HSPK_TOTAL_MISMATCH"), got)        # K-275: equipment (63,375) left out
        self.assertIn(("BS18", "LABEL_COEFFICIENT_MISMATCH"), got) # title 150 kg rebar vs coefficient 15.75 kg
        self.assertIn(("BS07", "DUPLICATE_COMPONENTS"), got)       # 1:4 identical to 1:3

    def test_k275_difference_is_the_equipment_total(self):
        f = next(f for f in self.findings if f.row == "BS14" and f.check == "HSPK_TOTAL_MISMATCH")
        self.assertTrue(f.evidence.get("equals_equipment_total"))
        self.assertAlmostEqual(f.evidence["difference"], 63375.0)

    def test_clean_items_are_not_flagged(self):
        flagged = {f.row for f in self.findings}
        for clean in ("BS12", "BS13", "BS21", "BS23", "BS29", "BS36", "BS17"):   # BS17 has ~1% source rounding only
            self.assertNotIn(clean, flagged)
        self.assertEqual(len(self.findings), 4)

    def test_every_item_total_is_reproducible_from_components_except_flagged_ones(self):
        flagged = {f.row for f in self.findings if f.check == "HSPK_TOTAL_MISMATCH"}
        for _, it in self.ref.items.iterrows():
            if it.item_id in flagged:
                continue
            self.assertAlmostEqual(self.ref.components_of(it.item_id).jumlah_printed.sum(), it.nilai_hspk, delta=1)


if __name__ == "__main__":
    unittest.main()
