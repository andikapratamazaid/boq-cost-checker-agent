import csv
import os
import tempfile
import unittest

from boqcheck.boq import load_boq
from boqcheck.util import norm_text, norm_unit, parse_number, units_compatible
from scripts.make_synthetic_boq import build, write_boq


class TestNumbers(unittest.TestCase):
    def test_parse_number(self):
        cases = {"1.234.567,89": 1234567.89, "Rp 2.500.000": 2500000.0, "1234.5": 1234.5, "1,5": 1.5,
                 "(1.000)": -1000.0, "1.234": 1234.0, "12.5": 12.5, "0.125": 0.125, "1234.567": 1234.567, "-": None, "": None, None: None, 7: 7.0, "1,234,567.89": 1234567.89}
        for raw, want in cases.items():
            with self.subTest(raw):
                self.assertEqual(parse_number(raw), want)
        self.assertEqual(parse_number("1.234", locale="id"), 1234.0)
        self.assertEqual(parse_number("1,234", locale="en"), 1234.0)

    def test_units(self):
        for a, b in [("M3", "m3"), ("m³", "m3"), ("m'", "m1"), ("Buah", "bh"), ("Kg", "kg"), ("M2", "m²")]:
            with self.subTest((a, b)):
                self.assertTrue(units_compatible(a, b))
        for a, b in [("m3", "m2"), ("kg", "ton"), ("m2", "m1")]:
            with self.subTest((a, b)):
                self.assertFalse(units_compatible(a, b))
        self.assertEqual(norm_unit(" M 3 "), "m3")

    def test_text_normalisation_keeps_specs(self):
        self.assertEqual(norm_text("Pekerjaan Beton K-225"), norm_text("pek. beton K 225"))
        self.assertNotEqual(norm_text("Beton K-225"), norm_text("Beton K-250"))
        self.assertIn("mix4", norm_text("Dinding 1 Pc : 4 Pp"))
        self.assertIn("mix4", norm_text("Dinding 1Pc:4Pp"))
        self.assertIn("setengah", norm_text("tebal 1/2 bata"))
        self.assertIn("40x40", norm_text("Keramik 40 x 40 cm"))


class TestBoqParser(unittest.TestCase):
    def test_xlsx_and_csv_parse_identically_and_classify_rows(self):
        d = build(3)
        with tempfile.TemporaryDirectory() as tmp:
            x, c = os.path.join(tmp, "a.xlsx"), os.path.join(tmp, "a.csv")
            write_boq(d, x, c)
            bx, bc = load_boq(x), load_boq(c)
        self.assertEqual(list(bx.rows.kind), list(bc.rows.kind))
        kinds = bx.rows.kind.value_counts().to_dict()
        for k in ("section", "item", "subtotal", "total", "ppn", "grand"):
            self.assertIn(k, kinds)
        self.assertEqual(kinds["total"], 1)
        # row ids are real sheet row numbers (header on row 4)
        self.assertEqual(int(bx.rows.row_id.min()), 5)

    def test_missing_header_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "bad.csv")
            with open(p, "w", newline="") as f:
                csv.writer(f).writerows([["a", "b"], ["1", "2"]])
            with self.assertRaises(ValueError):
                load_boq(p)


if __name__ == "__main__":
    unittest.main()
