"""Deterministic BoQ checks. Every number in a finding comes from this code, never from a language model."""
from __future__ import annotations

import pandas as pd

from .boq import BoQ
from .findings import Config, Finding
from .matcher import FuzzyMatcher, MatchResult
from .reference import Reference, validate_reference
from .util import norm_text, norm_unit, units_compatible


def run_checks(boq: BoQ, ref: Reference, cfg: Config | None = None, matcher: FuzzyMatcher | None = None,
               overrides: dict | None = None) -> tuple[list[Finding], pd.DataFrame]:
    """Return (findings, matches). overrides maps row_id -> reference item_id (or None to force 'no match'),
    which is how the agent resolves ambiguous items."""
    cfg = cfg or Config()
    matcher = matcher or FuzzyMatcher(ref, cfg)
    overrides = overrides or {}
    findings: list[Finding] = []
    counter = {"n": 0}

    def add(check, sev, row, item, msg, expected=None, actual=None, evidence=None, action=""):
        counter["n"] += 1
        findings.append(Finding(f"F{counter['n']:03d}", "boq", check, sev, row, item, msg, expected, actual,
                                evidence or {}, action))

    ref_issues: dict[str, list[str]] = {}
    for f in validate_reference(ref):
        ref_issues.setdefault(str(f.row), []).append(f.check)

    items = boq.items
    # ---- line-level arithmetic and completeness -------------------------------------------------
    for _, r in items.iterrows():
        v, h, j = r.volume, r.harga_satuan, r.jumlah
        if pd.isna(v) or v is None or v <= 0:
            add("MISSING_VALUE", "high", r.row_id, r.uraian, "Volume is missing, zero or negative.", None, v,
                {"field": "volume"}, "Fill in the volume or remove the line.")
        if pd.isna(h) or h is None or h <= 0:
            add("MISSING_VALUE", "high", r.row_id, r.uraian, "Unit price is missing, zero or negative.", None, h,
                {"field": "harga_satuan"}, "Fill in the unit price.")
        if all(pd.notna(x) and x is not None for x in (v, h, j)) and v > 0 and h > 0:
            expected = v * h
            if abs(expected - j) > cfg.line_tol_rp:
                rel = abs(expected - j) / max(abs(expected), 1.0)
                add("LINE_TOTAL_MISMATCH", "high" if rel >= 0.05 else "medium", r.row_id, r.uraian,
                    f"Volume x unit price = {expected:,.0f} but the line total is {j:,.0f}.", expected, j,
                    {"difference": j - expected, "pct": rel * 100}, "Correct the line total or the inputs.")

    # ---- duplicates --------------------------------------------------------------------------------
    seen: dict = {}
    for _, r in items.iterrows():
        key = (tuple(norm_text(r.uraian)), norm_unit(r.satuan), r.volume, r.harga_satuan)
        if key in seen:
            add("DUPLICATE_ITEM", "medium", r.row_id, r.uraian,
                f"Same description, unit, volume and price as row {seen[key]}: possible double counting.",
                evidence={"duplicate_of_row": seen[key]}, action="Confirm the item is intended twice.")
        else:
            seen[key] = r.row_id

    # ---- section subtotal, total, PPN, grand total (using the DISPLAYED numbers) ----------------------
    sub_rows = boq.rows[boq.rows.kind == "subtotal"]
    sections = list(dict.fromkeys(boq.rows[boq.rows.kind == "item"].section))
    sub_sum = 0.0
    sub_seen = 0
    for _, s in sub_rows.iterrows():
        sec = _section_before(boq.rows, s.row_id)
        lines = items[items.section == sec].jumlah.fillna(0).sum()
        if pd.notna(s.jumlah):
            sub_seen += 1
            sub_sum += s.jumlah
            if abs(lines - s.jumlah) > cfg.sum_tol_rp:
                add("SECTION_SUBTOTAL_MISMATCH", "high", s.row_id, s.uraian,
                    f"Sum of the section's line totals is {lines:,.0f} but the subtotal shows {s.jumlah:,.0f}.",
                    lines, s.jumlah, {"difference": s.jumlah - lines, "section": sec})
    total = boq.recap("total")
    base = None
    if total is not None and pd.notna(total.jumlah):
        base = sub_sum if sub_seen else items.jumlah.fillna(0).sum()
        if abs(base - total.jumlah) > cfg.sum_tol_rp:
            add("TOTAL_MISMATCH", "high", total.row_id, total.uraian,
                f"Sum of the {'subtotals' if sub_seen else 'line totals'} is {base:,.0f} but the total shows {total.jumlah:,.0f}.",
                base, total.jumlah, {"difference": total.jumlah - base})
    ppn = boq.recap("ppn")
    if ppn is not None and total is not None and pd.notna(ppn.jumlah) and pd.notna(total.jumlah):
        expected = total.jumlah * cfg.ppn_rate
        if abs(expected - ppn.jumlah) > cfg.sum_tol_rp:
            add("PPN_MISMATCH", "high", ppn.row_id, ppn.uraian,
                f"PPN at {cfg.ppn_rate:.0%} of the displayed total is {expected:,.0f} but the sheet shows {ppn.jumlah:,.0f}.",
                expected, ppn.jumlah, {"rate_used": cfg.ppn_rate, "implied_rate": ppn.jumlah / total.jumlah},
                "Check the PPN rate / basis that applies to this contract.")
    grand = boq.recap("grand")
    if grand is not None and total is not None and ppn is not None and pd.notna(grand.jumlah):
        expected = total.jumlah + ppn.jumlah
        if abs(expected - grand.jumlah) > cfg.sum_tol_rp:
            add("GRAND_TOTAL_MISMATCH", "high", grand.row_id, grand.uraian,
                f"Total + PPN is {expected:,.0f} but the grand total shows {grand.jumlah:,.0f}.", expected, grand.jumlah,
                {"difference": grand.jumlah - expected})

    # ---- reference comparison -------------------------------------------------------------------------
    rows = []
    for _, r in items.iterrows():
        if r.row_id in overrides:
            iid = overrides[r.row_id]
            m = MatchResult([(iid, 1.0)] if iid else [], iid, "matched" if iid else "unmatched")
            origin = "agent"
        else:
            m = matcher.match(r.uraian)
            origin = "fuzzy"
        rows.append(dict(row_id=r.row_id, uraian=r.uraian, ref_item_id=m.item_id, status=m.status,
                         score=m.best_score, origin=origin,
                         candidates=";".join(f"{i}:{s}" for i, s in m.candidates[:3])))
        if m.item_id is None:
            add("UNMATCHED_ITEM" if m.status == "unmatched" else "AMBIGUOUS_MATCH", "info", r.row_id, r.uraian,
                "No confident reference match; price and unit were not compared."
                if m.status == "unmatched" else "Several reference items fit about equally; price and unit were not compared.",
                evidence={"candidates": m.candidates[:3]}, action="Match manually or ask the agent to resolve it.")
            continue
        it = ref.item(m.item_id)
        if not units_compatible(r.satuan, it["satuan"]):
            add("UNIT_MISMATCH", "high", r.row_id, r.uraian,
                f"Unit '{r.satuan}' does not match the reference unit '{it['satuan']}' for '{it['uraian']}'.",
                evidence={"ref_item_id": m.item_id, "ref_unit": it["satuan"], "match_score": m.best_score},
                action="Check the unit and the volume basis; the price cannot be compared.")
            continue
        if pd.isna(r.harga_satuan) or r.harga_satuan is None or r.harga_satuan <= 0:
            continue
        ratio = r.harga_satuan / float(it["nilai_hspk"])
        ev = {"ref_item_id": m.item_id, "ref_uraian": it["uraian"], "hspk": float(it["nilai_hspk"]), "ratio": ratio,
              "match_score": m.best_score, "match_origin": origin}
        if m.item_id in ref_issues:
            ev["reference_data_issues"] = ref_issues[m.item_id]
        if ratio > cfg.price_high_ratio:
            add("PRICE_HIGH", "high" if ratio >= cfg.high_severity_ratio else "medium", r.row_id, r.uraian,
                f"Unit price {r.harga_satuan:,.0f} is {ratio:.2f}x the reference HSPK {it['nilai_hspk']:,.0f}.",
                float(it["nilai_hspk"]), r.harga_satuan, ev, "Ask for the price analysis (AHSP) behind this unit price.")
        elif ratio < cfg.price_low_ratio:
            add("PRICE_LOW", "high" if ratio <= cfg.low_severity_ratio else "medium", r.row_id, r.uraian,
                f"Unit price {r.harga_satuan:,.0f} is only {ratio:.2f}x the reference HSPK {it['nilai_hspk']:,.0f}.",
                float(it["nilai_hspk"]), r.harga_satuan, ev,
                "Check for a missing component, a wrong unit or a decimal slip.")
    return findings, pd.DataFrame(rows)


def _section_before(rows: pd.DataFrame, row_id: int) -> str:
    prev = rows[(rows.row_id < row_id) & (rows.kind == "item")]
    return prev.iloc[-1].section if len(prev) else ""
