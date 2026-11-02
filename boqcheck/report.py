"""Deterministic Markdown report (no LLM needed)."""
from __future__ import annotations

from .findings import Finding

ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def markdown_report(findings: list[Finding], title: str = "BoQ check report", reference_source: str = "") -> str:
    real = [f for f in findings if f.severity != "info"]
    info = [f for f in findings if f.severity == "info"]
    L = [f"# {title}", ""]
    if reference_source:
        L += [f"Reference prices: {reference_source}. HSPK is a regional price ceiling/benchmark, not an auditor's verdict; "
              "every flag is a prompt for human review.", ""]
    counts = {}
    for f in real:
        counts[f.check] = counts.get(f.check, 0) + 1
    L += [f"**{len(real)} issue(s) flagged**, {len(info)} item(s) not compared with the reference.", ""]
    if counts:
        L += ["| Check | Count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])] + [""]
    L += ["## Findings", "", "| ID | Severity | Check | Row | Item | Detail |", "|---|---|---|---|---|---|"]
    for f in sorted(real, key=lambda f: (ORDER[f.severity], str(f.row))):
        L.append(f"| {f.finding_id} | {f.severity} | {f.check} | {f.row} | {f.item[:48]} | {f.message} |")
    if info:
        L += ["", "## Not compared (no confident reference match)", ""]
        L += [f"- row {f.row}: {f.item[:70]}" for f in info]
    return "\n".join(L) + "\n"
