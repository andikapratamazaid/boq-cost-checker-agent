"""  python -m boqcheck.cli check data/boq/sample_boq.xlsx            (deterministic, no API key)
     python -m boqcheck.cli check data/boq/sample_boq.xlsx --agent    (adds the LLM audit report; needs ANTHROPIC_API_KEY)
     python -m boqcheck.cli reference                                  (validate the reference price data itself)
"""
from __future__ import annotations

import argparse

from .agent import AuditSession, run_agent
from .boq import load_boq
from .checks import run_checks
from .findings import Config
from .reference import load_reference, validate_reference
from .report import markdown_report


def main() -> None:
    ap = argparse.ArgumentParser(description="BoQ / RAB cost checker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("path"); c.add_argument("--ppn", type=float, default=None)
    c.add_argument("--agent", action="store_true"); c.add_argument("--out", default=None)
    sub.add_parser("reference")
    a = ap.parse_args()
    ref = load_reference()
    if a.cmd == "reference":
        print(markdown_report(validate_reference(ref), "Reference data validation", ref.source))
        return
    cfg = Config(ppn_rate=a.ppn) if a.ppn is not None else Config()
    boq = load_boq(a.path)
    if a.agent:
        from .llm import AnthropicClient
        res = run_agent(AuditSession(boq, ref, cfg), AnthropicClient())
        text = res.report + (f"\n\n[citation check] invalid: {res.invalid_citations or 'none'}; "
                             f"high-severity findings not mentioned: {res.uncited_high or 'none'}\n")
    else:
        findings, _ = run_checks(boq, ref, cfg)
        text = markdown_report(findings, f"BoQ check: {a.path}", ref.source)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
