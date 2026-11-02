"""The BoQ audit agent: an LLM that investigates findings with read-only tools and writes the report.

Division of labour
  code  : parsing, arithmetic, reference comparison, finding IDs and every number
  model : resolving ambiguous item matches, judging which findings matter, explaining and prioritising
Guardrails: tools are read-only; the model cannot edit the BoQ or invent findings; the report is checked
for citations of finding IDs that do not exist and for high-severity findings it forgot to mention.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from .boq import BoQ
from .checks import run_checks
from .findings import Config, Finding
from .matcher import FuzzyMatcher
from .reference import Reference, validate_reference
from .llm import LLMClient

SYSTEM_PROMPT = """\
You are a careful quantity-surveying assistant that audits a Bill of Quantities (BoQ / RAB) for an Indonesian
construction project. Deterministic code has already parsed the sheet and produced FINDINGS (arithmetic errors,
unit mismatches, unit prices far from the reference HSPK, duplicates, missing values). You investigate and explain.

Rules
1. Start with get_overview, then list_findings. Use get_finding / get_boq_row / get_reference_item for detail.
2. Every number you state must come from a tool result. Never compute prices or totals yourself.
3. Cite finding IDs like [F012] for each issue you report. Do not cite an ID that no tool returned.
4. Items listed as AMBIGUOUS_MATCH or UNMATCHED_ITEM were not compared with the reference. For each, use
   search_reference. If one candidate clearly fits (same work type AND the same numeric specs such as concrete grade,
   mix ratio, thickness, size), call resolve_match, then report any new findings it returns. If unsure, leave it
   unresolved and say so. Never force a match.
5. HSPK is a regional price benchmark or ceiling. It is not proof of an error and it can itself contain mistakes:
   if a finding's evidence has reference_data_issues, say that the reference value is doubtful.
6. Describe issues as 'needs verification', never as fraud or intent.
7. Respect the assumptions: PPN rate, tolerance and price thresholds are configuration values shown by get_overview.
8. Reply in the language of the user's request (Indonesian or English).

Report format: (1) one-paragraph summary with counts; (2) HIGH-priority issues, most important first, each with the cited
finding ID, the evidence numbers and a recommended action; (3) MEDIUM issues; (4) items you could not compare;
(5) assumptions and limits. Keep it concise and factual.
"""

TOOLS = [
    {"name": "get_overview", "description": "BoQ structure counts, recap numbers, configuration thresholds and the reference source.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "list_findings", "description": "List findings (id, severity, check, row, item, message). Optional filters. Max 60 rows.",
     "input_schema": {"type": "object", "properties": {"severity": {"type": "string", "enum": ["high", "medium", "low", "info"]},
                                                      "check": {"type": "string"}}, "required": []}},
    {"name": "get_finding", "description": "Full detail of one finding including evidence.",
     "input_schema": {"type": "object", "properties": {"finding_id": {"type": "string"}}, "required": ["finding_id"]}},
    {"name": "get_boq_row", "description": "One BoQ line (as displayed) and its current reference match.",
     "input_schema": {"type": "object", "properties": {"row_id": {"type": "integer"}}, "required": ["row_id"]}},
    {"name": "search_reference", "description": "Find reference (HSPK) items similar to a text. Returns top 5 with score, unit and HSPK.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_reference_item", "description": "A reference item with its components and any known data-quality issues.",
     "input_schema": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]}},
    {"name": "resolve_match", "description": "Declare that a BoQ row corresponds to a reference item (or 'none'). Re-runs the checks for the sheet and returns the findings for that row.",
     "input_schema": {"type": "object", "properties": {"row_id": {"type": "integer"}, "item_id": {"type": "string", "description": "reference item id, or 'none'"}},
                      "required": ["row_id", "item_id"]}},
]


class AuditSession:
    def __init__(self, boq: BoQ, ref: Reference, cfg: Config | None = None):
        self.boq, self.ref, self.cfg = boq, ref, cfg or Config()
        self.matcher = FuzzyMatcher(ref, self.cfg)
        self.overrides: dict = {}
        self.resolutions: list[dict] = []
        self.ref_findings = validate_reference(ref)
        self.refresh()

    def refresh(self):
        self.findings, self.matches = run_checks(self.boq, self.ref, self.cfg, self.matcher, self.overrides)
        self.by_id = {f.finding_id: f for f in self.findings}

    # --- tools -------------------------------------------------------------------------------------------
    def call(self, name: str, args: dict) -> tuple[str, bool]:
        try:
            fn = getattr(self, f"_t_{name}", None)
            if fn is None:
                return f"ERROR: unknown tool '{name}'", True
            return fn(**(args or {}))
        except TypeError as e:
            return f"ERROR: bad arguments: {e}", True
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}", True

    def _t_get_overview(self):
        r = self.boq.rows
        recap = {k: (None if self.boq.recap(k) is None else float(self.boq.recap(k).jumlah)) for k in ("total", "ppn", "grand")}
        sev = {}
        for f in self.findings:
            sev[f.severity] = sev.get(f.severity, 0) + 1
        out = {"rows": int(len(r)), "items": int((r.kind == "item").sum()), "sections": int((r.kind == "section").sum()),
               "recap_as_displayed": recap, "findings_by_severity": sev,
               "config": {"ppn_rate": self.cfg.ppn_rate, "price_high_ratio": self.cfg.price_high_ratio,
                          "price_low_ratio": self.cfg.price_low_ratio, "line_tolerance_rp": self.cfg.line_tol_rp},
               "reference": self.ref.source, "reference_items": int(len(self.ref.items)),
               "note": "HSPK is a benchmark/ceiling, not proof of error."}
        return json.dumps(out, ensure_ascii=False), False

    def _t_list_findings(self, severity=None, check=None):
        fs = [f for f in self.findings if (not severity or f.severity == severity) and (not check or f.check == check)]
        rows = [f"{f.finding_id} | {f.severity} | {f.check} | row {f.row} | {f.item[:45]} | {f.message}" for f in fs[:60]]
        more = f"\n... {len(fs) - 60} more (filter by severity or check)" if len(fs) > 60 else ""
        return (f"{len(fs)} finding(s)\n" + "\n".join(rows) + more) if fs else "0 findings", False

    def _t_get_finding(self, finding_id):
        f = self.by_id.get(finding_id)
        return (json.dumps(f.to_dict(), ensure_ascii=False, default=str), False) if f else (f"ERROR: no finding '{finding_id}'", True)

    def _t_get_boq_row(self, row_id):
        r = self.boq.rows[self.boq.rows.row_id == row_id]
        if r.empty:
            return f"ERROR: no row {row_id}", True
        d = r.iloc[0].to_dict()
        m = self.matches[self.matches.row_id == row_id]
        d["match"] = m.iloc[0].to_dict() if len(m) else None
        return json.dumps(d, ensure_ascii=False, default=str), False

    def _t_search_reference(self, query):
        out = []
        for iid, sc in self.matcher.candidates(query, 5):
            it = self.ref.item(iid)
            out.append(f"{iid} | score {sc} | {it['uraian']} | unit {it['satuan']} | HSPK {it['nilai_hspk']:,.0f}")
        return "\n".join(out), False

    def _t_get_reference_item(self, item_id):
        it = self.ref.item(item_id)
        if not it:
            return f"ERROR: no reference item '{item_id}'", True
        comps = self.ref.components_of(item_id)
        lines = [f"{r.kategori} | {r.komponen} | coef {r.koefisien} {r.satuan} x {r.harga_satuan:,.0f} = {r.jumlah_printed:,.0f}" for _, r in comps.iterrows()]
        issues = [f"{f.check}: {f.message}" for f in self.ref_findings if str(f.row) == item_id]
        return (f"{item_id} | {it['uraian']} | unit {it['satuan']} | HSPK {it['nilai_hspk']:,.0f}\n" + "\n".join(lines)
                + ("\nREFERENCE DATA ISSUES:\n" + "\n".join(issues) if issues else "")), False

    def _t_resolve_match(self, row_id, item_id):
        if row_id not in set(self.boq.items.row_id):
            return f"ERROR: row {row_id} is not an item line", True
        target = None if str(item_id).lower() == "none" else item_id
        if target and not self.ref.item(target):
            return f"ERROR: no reference item '{item_id}'", True
        self.overrides[row_id] = target
        self.resolutions.append({"row_id": row_id, "item_id": target})
        self.refresh()
        fs = [f for f in self.findings if f.scope == "boq" and f.row == row_id]
        body = "\n".join(f"{f.finding_id} | {f.severity} | {f.check} | {f.message}" for f in fs) or "no findings for this row after matching"
        return f"Resolved row {row_id} -> {target}. Findings for the row:\n{body}", False


@dataclass
class AuditResult:
    report: str
    steps: int = 0
    tool_calls: int = 0
    stopped_reason: str = "final"
    cited_ids: list = field(default_factory=list)
    invalid_citations: list = field(default_factory=list)
    uncited_high: list = field(default_factory=list)
    resolutions: list = field(default_factory=list)
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


def run_agent(session: AuditSession, llm: LLMClient, request: str = "Audit this BoQ and write the report.",
              max_steps: int = 14) -> AuditResult:
    t0 = time.monotonic()
    messages = [{"role": "user", "content": request}]
    res = AuditResult(report="", stopped_reason="max_steps")
    for _ in range(max_steps):
        resp = llm.create(SYSTEM_PROMPT, messages, TOOLS)
        res.steps += 1
        u = resp.get("usage") or {}
        res.input_tokens += u.get("input_tokens", 0); res.output_tokens += u.get("output_tokens", 0)
        messages.append({"role": "assistant", "content": resp["content"]})
        uses = [b for b in resp["content"] if b.get("type") == "tool_use"]
        text = "\n".join(b["text"] for b in resp["content"] if b.get("type") == "text").strip()
        if not uses:
            res.report, res.stopped_reason = text, "final"
            break
        results = []
        for tu in uses:
            out, err = session.call(tu["name"], tu.get("input") or {})
            res.tool_calls += 1
            blk = {"type": "tool_result", "tool_use_id": tu["id"], "content": out}
            if err:
                blk["is_error"] = True
            results.append(blk)
        messages.append({"role": "user", "content": results})
    else:
        res.report = "Step limit reached before a report was produced."
    cited = sorted(set(re.findall(r"\bF\d{3}\b", res.report)))
    res.cited_ids = cited
    res.invalid_citations = [c for c in cited if c not in session.by_id]
    res.uncited_high = [f.finding_id for f in session.findings if f.severity == "high" and f.finding_id not in cited]
    res.resolutions = session.resolutions
    res.latency_s = time.monotonic() - t0
    return res
