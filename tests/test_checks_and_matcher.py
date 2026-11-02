import unittest

from boqcheck.checks import run_checks
from boqcheck.findings import Config
from boqcheck.matcher import FuzzyMatcher
from boqcheck.reference import load_reference

from .helpers import make_boq

REF = load_reference()
HSPK_K225 = 1452280


def checks_of(rows, cfg=None, overrides=None):
    f, m = run_checks(make_boq(rows), REF, cfg, overrides=overrides)
    return f, m


def kinds(f):
    return {(x.check) for x in f if x.severity != "info"}


class TestLineChecks(unittest.TestCase):
    def item(self, price, vol=12.34, unit="m3", text="Pekerjaan Beton K-225", jumlah=None):
        return [("section", "A", "", None, None, None),
                ("item", text, unit, vol, price, round(vol * price) if jumlah is None else jumlah)]

    def test_clean_line_and_rounding_are_not_flagged(self):
        self.assertEqual(kinds(checks_of(self.item(1600000)[0:2])[0]), set())
        # a rupiah of rounding difference is tolerated; five rupiah is not
        self.assertEqual(kinds(checks_of(self.item(1600000, jumlah=round(12.34 * 1600000) + 1))[0]), set())
        self.assertEqual(kinds(checks_of(self.item(1600000, jumlah=round(12.34 * 1600000) + 5))[0]), {"LINE_TOTAL_MISMATCH"})

    def test_price_thresholds(self):
        for ratio, expect in [(1.0, set()), (1.29, set()), (1.31, {"PRICE_HIGH"}), (0.61, set()), (0.59, {"PRICE_LOW"}), (0.9, set())]:
            with self.subTest(ratio):
                self.assertEqual(kinds(checks_of(self.item(int(HSPK_K225 * ratio)))[0]), expect)

    def test_severity_scales_with_distance(self):
        f = checks_of(self.item(int(HSPK_K225 * 3)))[0]
        self.assertEqual([x.severity for x in f if x.check == "PRICE_HIGH"], ["high"])
        f = checks_of(self.item(int(HSPK_K225 * 1.4)))[0]
        self.assertEqual([x.severity for x in f if x.check == "PRICE_HIGH"], ["medium"])

    def test_unit_mismatch_but_synonyms_are_fine(self):
        self.assertEqual(kinds(checks_of(self.item(HSPK_K225, unit="m2"))[0]), {"UNIT_MISMATCH"})
        for u in ("M3", "m³", "m3 "):
            self.assertEqual(kinds(checks_of(self.item(HSPK_K225, unit=u))[0]), set())

    def test_missing_volume_and_price(self):
        rows = [("section", "A", "", None, None, None), ("item", "Pekerjaan Beton K-225", "m3", None, 1500000, 18000000)]
        self.assertEqual(kinds(checks_of(rows)[0]), {"MISSING_VALUE"})
        rows = [("section", "A", "", None, None, None), ("item", "Pekerjaan Beton K-225", "m3", 5.0, 0, 0)]
        self.assertEqual(kinds(checks_of(rows)[0]), {"MISSING_VALUE"})

    def test_duplicates_only_when_everything_matches(self):
        a = ("item", "Pekerjaan Beton K-225", "m3", 10.0, 1500000, 15000000)
        same = [("section", "A", "", None, None, None), a, a]
        self.assertEqual(kinds(checks_of(same)[0]), {"DUPLICATE_ITEM"})
        other_volume = [("section", "A", "", None, None, None), a, ("item", "Pekerjaan Beton K-225", "m3", 11.0, 1500000, 16500000)]
        self.assertEqual(kinds(checks_of(other_volume)[0]), set())

    def test_items_without_reference_are_info_not_errors(self):
        rows = [("section", "A", "", None, None, None), ("item", "Mobilisasi dan demobilisasi", "ls", 1.0, 25000000, 25000000),
                ("item", "Pekerjaan Beton K-300", "m3", 10.0, 1600000, 16000000)]
        f, m = checks_of(rows)
        self.assertEqual(kinds(f), set())
        self.assertEqual(set(m.status), {"unmatched"})


class TestRecap(unittest.TestCase):
    def sheet(self, sub=1000000, total=1000000, ppn=110000, grand=1110000):
        return [("section", "A", "", None, None, None),
                ("item", "Pekerjaan Beton K-225", "m3", 1.0, 1000000, 1000000),
                ("subtotal", "Jumlah A", "", None, None, sub),
                ("total", "TOTAL (sebelum PPN)", "", None, None, total),
                ("ppn", "PPN 11%", "", None, None, ppn),
                ("grand", "TOTAL + PPN", "", None, None, grand)]

    def test_clean_recap(self):
        self.assertEqual(kinds(checks_of(self.sheet())[0]), set())

    def test_each_recap_error_is_reported_once(self):
        self.assertEqual(kinds(checks_of(self.sheet(sub=900000, total=900000, ppn=99000, grand=999000))[0]), {"SECTION_SUBTOTAL_MISMATCH"})
        self.assertEqual(kinds(checks_of(self.sheet(total=1100000, ppn=121000, grand=1221000))[0]), {"TOTAL_MISMATCH"})
        self.assertEqual(kinds(checks_of(self.sheet(ppn=120000, grand=1120000))[0]), {"PPN_MISMATCH"})
        self.assertEqual(kinds(checks_of(self.sheet(grand=1200000))[0]), {"GRAND_TOTAL_MISMATCH"})

    def test_ppn_rate_is_configurable(self):
        s = self.sheet(ppn=120000, grand=1120000)
        self.assertEqual(kinds(checks_of(s, Config(ppn_rate=0.12))[0]), set())


class TestMatcherAndOverrides(unittest.TestCase):
    def setUp(self):
        self.m = FuzzyMatcher(REF)

    def test_variants_find_the_right_item(self):
        cases = {"Pek. Beton K 225": "BS12", "PEKERJAAN BETON K250": "BS13", "Pasangan bata merah 1:4 tbl 1/2 bata": "BS21",
                 "Pemasangan Dinding Batu Merah 1Pc:4Pp tebal 1 bata": "BS23", "Pek. Bekisting Sloof": "BS16",
                 "Pemasangan Keramik 40 x 40 cm": "BS30", "Pengecatan tembok baru": "BS28"}
        for text, want in cases.items():
            with self.subTest(text):
                self.assertEqual(self.m.match(text).item_id, want)

    def test_near_miss_items_are_not_force_matched(self):
        for text in ("Pekerjaan Beton K-300", "Pemasangan Keramik 60x60 cm", "Dinding bata merah 1:6 tebal 1/2 bata",
                     "Pemasangan Kaca Tebal 8 mm", "Mobilisasi dan demobilisasi"):
            with self.subTest(text):
                self.assertIsNone(self.m.match(text).item_id)

    def test_override_resolves_an_unmatched_row(self):
        rows = [("section", "A", "", None, None, None), ("item", "Besi beton ulir", "kg", 1000.0, 90000, 90000000)]
        f, m = checks_of(rows)
        self.assertEqual(kinds(f), set())                       # not compared: no confident match
        f, m = checks_of(rows, overrides={6: "BS15"})           # agent says: pembesian, HSPK 21,636/kg
        self.assertEqual(kinds(f), {"PRICE_HIGH"})
        self.assertEqual(m.iloc[0].origin, "agent")


if __name__ == "__main__":
    unittest.main()
