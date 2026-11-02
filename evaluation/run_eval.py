"""Score the deterministic detector against injected errors (no LLM, no network).

  python -m evaluation.run_eval --n 50
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

from boqcheck.boq import load_boq
from boqcheck.checks import run_checks
from boqcheck.findings import Config
from boqcheck.matcher import FuzzyMatcher
from boqcheck.reference import load_reference
from scripts.make_synthetic_boq import build, write_boq

CHECKS = ["LINE_TOTAL_MISMATCH", "PRICE_HIGH", "PRICE_LOW", "UNIT_MISMATCH", "MISSING_VALUE", "DUPLICATE_ITEM",
          "SECTION_SUBTOTAL_MISMATCH", "TOTAL_MISMATCH", "PPN_MISMATCH", "GRAND_TOTAL_MISMATCH"]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = (2 * p * r / (p + r)) if p and r else (0.0 if (p is not None and r is not None) else None)
    return p, r, f


def evaluate(n: int, cfg: Config | None = None, ref=None, datasets=None, oracle_resolver: bool = False):
    ref = ref or load_reference()
    cfg = cfg or Config()
    matcher = FuzzyMatcher(ref, cfg)
    stats = defaultdict(lambda: [0, 0, 0])                 # check -> tp, fp, fn
    tier_stats = defaultdict(lambda: [0, 0])               # (check, tier) -> detected, total
    fps, match = [], dict(ref_rows=0, correct=0, wrong=0, not_matched=0, custom_rows=0, custom_false_match=0)
    n_lines = n_injected = 0
    with tempfile.TemporaryDirectory() as tmp:
        for seed in range(n):
            d = (datasets[seed] if datasets else build(seed, ref))
            path = str(Path(tmp) / f"b{seed}.xlsx")
            write_boq(d, xlsx_path=path)
            boq = load_boq(path)                           # goes through the real xlsx parser
            overrides = dict(d['match_truth']) if oracle_resolver else None
            findings, matches = run_checks(boq, ref, cfg, matcher, overrides)
            truth = {(t["row_id"], t["check"]): t["tier"] for t in d["truth"]}
            got = {(int(f.row), f.check): f for f in findings if f.scope == "boq" and f.severity != "info"}
            n_lines += len(boq.items); n_injected += len(truth)
            for key, tier in truth.items():
                hit = key in got
                stats[key[1]][0 if hit else 2] += 1
                tier_stats[(key[1], tier)][1] += 1
                tier_stats[(key[1], tier)][0] += int(hit)
            for key, f in got.items():
                if key not in truth:
                    stats[key[1]][1] += 1
                    fps.append(dict(seed=seed, row=key[0], check=key[1], item=f.item, message=f.message))
            mt = d["match_truth"]
            for _, m in matches.iterrows():
                if m.row_id in mt:
                    match["ref_rows"] += 1
                    if pd.isna(m.ref_item_id): match["not_matched"] += 1
                    elif m.ref_item_id == mt[m.row_id]: match["correct"] += 1
                    else: match["wrong"] += 1
                else:
                    match["custom_rows"] += 1
                    if pd.notna(m.ref_item_id): match["custom_false_match"] += 1
    return dict(stats={k: list(v) for k, v in stats.items()}, tier={f"{k[0]}|{k[1]}": v for k, v in tier_stats.items()},
                false_positives=fps, match=match, n_boqs=n, n_lines=n_lines, n_injected=n_injected)


def summarize(res: dict) -> dict:
    tp = sum(v[0] for v in res["stats"].values()); fp = sum(v[1] for v in res["stats"].values()); fn = sum(v[2] for v in res["stats"].values())
    p, r, f = prf(tp, fp, fn)
    return dict(precision=p, recall=r, f1=f, tp=tp, fp=fp, fn=fn)


def markdown(res, overall, sweep, cfg: Config, upper=None) -> str:
    pc = lambda x: "n/a" if x is None else f"{x*100:.1f}%"
    L = ["# Detection evaluation (synthetic BoQs with injected errors)", "",
         f"- BoQs: {res['n_boqs']} | item lines: {res['n_lines']} | injected errors: {res['n_injected']}",
         f"- Thresholds: price high > {cfg.price_high_ratio}x HSPK, low < {cfg.price_low_ratio}x; PPN {cfg.ppn_rate:.0%}; line tolerance Rp {cfg.line_tol_rp:g}", "",
         f"**Overall: precision {pc(overall['precision'])}, recall {pc(overall['recall'])}, F1 {pc(overall['f1'])}** "
         f"(TP {overall['tp']}, FP {overall['fp']}, FN {overall['fn']})", "",
         "| Check | Injected | Detected | Recall | False positives | Precision |", "|---|---|---|---|---|---|"]
    for c in CHECKS:
        tp, fp, fn = res["stats"].get(c, [0, 0, 0]); p, r, _ = prf(tp, fp, fn)
        L.append(f"| {c} | {tp+fn} | {tp} | {pc(r)} | {fp} | {pc(p)} |")
    if upper:
        L += ["", f"**Upper bound with a perfect item resolver** (every reference-backed line matched correctly, which is the job "
              f"left to the agent): precision {pc(upper['precision'])}, recall {pc(upper['recall'])}. "
              "The gap between the two recall figures is the headroom the agent can add; it is not measured here because "
              "that needs a live model."]
    L += ["", "## Recall by error tier", "", "| Check | Tier | Detected / Injected |", "|---|---|---|"]
    for k, (det, tot) in sorted(res["tier"].items()):
        c, t = k.split("|"); L.append(f"| {c} | {t} | {det} / {tot} |")
    m = res["match"]
    L += ["", "## Item matching (BoQ text -> reference item)", "",
          f"- Reference-backed lines: {m['ref_rows']} | correct: {m['correct']} ({pc(m['correct']/m['ref_rows'] if m['ref_rows'] else None)}) | "
          f"wrong: {m['wrong']} | not matched (left for the agent): {m['not_matched']}",
          f"- Custom lines with no reference item: {m['custom_rows']} | wrongly matched: {m['custom_false_match']}", "",
          "## Price threshold sweep (PRICE_HIGH / PRICE_LOW only)", "", "| high ratio | low ratio | precision | recall |", "|---|---|---|---|"]
    for s in sweep:
        L.append(f"| {s['high']} | {s['low']} | {pc(s['p'])} | {pc(s['r'])} |")
    L += ["", "## False positives (first 15)", ""]
    L += [f"- seed {f['seed']} row {f['row']} {f['check']}: {f['item'][:50]}: {f['message']}" for f in res["false_positives"][:15]] or ["None."]
    L += ["", "> The honest-price band (0.80-1.22x HSPK) and the error factors are generator assumptions. "
          "Precision and recall here describe these error types only, not real-project error rates."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default="evaluation/results")
    a = ap.parse_args()
    ref = load_reference(); cfg = Config()
    datasets = [build(s, ref) for s in range(a.n)]
    res = evaluate(a.n, cfg, ref, datasets)
    overall = summarize(res)
    upper = summarize(evaluate(a.n, cfg, ref, datasets, oracle_resolver=True))
    sweep = []
    for hi, lo in [(1.15, 0.85), (1.22, 0.78), (1.30, 0.60), (1.40, 0.55), (1.50, 0.50), (1.70, 0.40)]:
        r2 = evaluate(a.n, Config(price_high_ratio=hi, price_low_ratio=lo), ref, datasets)
        tp = sum(r2["stats"].get(c, [0, 0, 0])[0] for c in ("PRICE_HIGH", "PRICE_LOW"))
        fp = sum(r2["stats"].get(c, [0, 0, 0])[1] for c in ("PRICE_HIGH", "PRICE_LOW"))
        fn = sum(r2["stats"].get(c, [0, 0, 0])[2] for c in ("PRICE_HIGH", "PRICE_LOW"))
        p, r, _ = prf(tp, fp, fn); sweep.append(dict(high=hi, low=lo, p=p, r=r))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "latest.md").write_text(markdown(res, overall, sweep, cfg, upper), encoding="utf-8")
    (out / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.json").write_text(json.dumps(dict(overall=overall, upper_bound=upper, **res, sweep=sweep), indent=1, default=str))
    print(markdown(res, overall, sweep, cfg, upper))


if __name__ == "__main__":
    main()
