import unittest

from boqcheck.reference import load_reference
from evaluation.run_eval import evaluate, summarize


class TestDetectionEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = load_reference()
        cls.res = evaluate(12, ref=cls.ref)

    def test_arithmetic_checks_are_perfect_on_injected_errors(self):
        for c in ("LINE_TOTAL_MISMATCH", "MISSING_VALUE", "DUPLICATE_ITEM", "SECTION_SUBTOTAL_MISMATCH", "TOTAL_MISMATCH", "PPN_MISMATCH"):
            tp, fp, fn = self.res["stats"].get(c, [0, 0, 0])
            with self.subTest(c):
                self.assertEqual((fp, fn), (0, 0))

    def test_no_false_positives_overall(self):
        self.assertEqual(summarize(self.res)["fp"], 0, self.res["false_positives"][:3])

    def test_matcher_is_conservative(self):
        m = self.res["match"]
        self.assertEqual(m["wrong"], 0)
        self.assertEqual(m["custom_false_match"], 0)
        self.assertGreater(m["correct"] / m["ref_rows"], 0.85)

    def test_perfect_resolver_closes_the_matching_gap(self):
        base = summarize(self.res)["recall"]
        upper = summarize(evaluate(12, ref=self.ref, oracle_resolver=True))
        self.assertGreaterEqual(upper["recall"], base)
        self.assertEqual(upper["fp"], 0)


if __name__ == "__main__":
    unittest.main()
