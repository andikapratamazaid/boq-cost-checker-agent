import subprocess
import sys
import unittest

from boqcheck.agent import AuditSession, run_agent
from boqcheck.boq import load_boq
from boqcheck.llm import ScriptedLLM
from boqcheck.reference import load_reference

from .helpers import make_boq

T, X = ScriptedLLM.tool, ScriptedLLM.text
REF = load_reference()
SAMPLE = "data/boq/sample_boq_synthetic.xlsx"


def sample_session():
    return AuditSession(load_boq(SAMPLE), REF)


class TestAgent(unittest.TestCase):
    def test_happy_path_and_citation_check(self):
        s = sample_session()
        high = [f.finding_id for f in s.findings if f.severity == "high"]
        report = "Summary. " + " ".join(f"Issue [{i}]." for i in high)
        r = run_agent(s, ScriptedLLM([T("get_overview", {}), T("list_findings", {"severity": "high"}), X(report)]))
        self.assertEqual(r.stopped_reason, "final")
        self.assertEqual(r.invalid_citations, [])
        self.assertEqual(r.uncited_high, [])
        self.assertEqual(r.tool_calls, 2)

    def test_invented_and_missing_citations_are_detected(self):
        s = sample_session()
        r = run_agent(s, ScriptedLLM([X("Only one issue [F999].")]))
        self.assertEqual(r.invalid_citations, ["F999"])
        self.assertTrue(r.uncited_high)

    def test_resolve_match_adds_findings_and_is_logged(self):
        boq = make_boq([("section", "A", "", None, None, None), ("item", "Besi beton ulir", "kg", 1000.0, 90000, 90000000)])
        s = AuditSession(boq, REF)
        self.assertEqual([f for f in s.findings if f.severity != "info"], [])
        out, err = s.call("resolve_match", {"row_id": 6, "item_id": "BS15"})
        self.assertFalse(err)
        self.assertIn("PRICE_HIGH", out)
        self.assertEqual(s.resolutions, [{"row_id": 6, "item_id": "BS15"}])

    def test_tool_errors_do_not_crash_the_loop(self):
        s = sample_session()
        for name, args in [("resolve_match", {"row_id": 99999, "item_id": "BS15"}), ("resolve_match", {"row_id": 6, "item_id": "NOPE"}),
                           ("get_finding", {"finding_id": "F999"}), ("get_reference_item", {"item_id": "X"}),
                           ("delete_everything", {}), ("get_boq_row", {})]:
            with self.subTest(name):
                out, err = s.call(name, args)
                self.assertTrue(err, out)

    def test_reference_item_tool_exposes_known_data_issues(self):
        out, err = sample_session().call("get_reference_item", {"item_id": "BS18"})
        self.assertFalse(err)
        self.assertIn("LABEL_COEFFICIENT_MISMATCH", out)

    def test_step_limit(self):
        r = run_agent(sample_session(), ScriptedLLM([T("get_overview", {})]), max_steps=3)
        self.assertEqual(r.stopped_reason, "max_steps")
        self.assertEqual(r.steps, 3)

    def test_the_agent_cannot_change_the_boq(self):
        s = sample_session()
        before = s.boq.rows.copy()
        s.call("resolve_match", {"row_id": 6, "item_id": "BS12"})
        self.assertTrue(before.equals(s.boq.rows))


class TestCli(unittest.TestCase):
    def test_deterministic_cli_runs_without_an_api_key(self):
        p = subprocess.run([sys.executable, "-m", "boqcheck.cli", "check", SAMPLE], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("issue(s) flagged", p.stdout)

    def test_reference_command_lists_the_known_source_issues(self):
        p = subprocess.run([sys.executable, "-m", "boqcheck.cli", "reference"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("LABEL_COEFFICIENT_MISMATCH", p.stdout)


if __name__ == "__main__":
    unittest.main()
