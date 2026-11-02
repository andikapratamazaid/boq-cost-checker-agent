# BoQ / RAB Cost Checker Agent

> Audits a construction Bill of Quantities (BoQ / RAB spreadsheet): catches arithmetic errors, wrong units, duplicates and unit prices that are far from a **real** government price reference (HSPK 2026). Deterministic checks produce every number; an LLM agent resolves ambiguous items and writes the report, and its citations are verified.

## Real data vs. synthetic data (read this first)
| Part | Data | Status |
|---|---|---|
| Reference prices (`data/reference/`) | **Real**: 38 work items and 260 cost components transcribed from Perbup Kab. Bengkulu Selatan No. 25/2025, HSPK Tahun Anggaran 2026 | Real excerpt, not the full price book; one regency only |
| Reference validation (`docs/reference_data_findings.md`) | Real findings about that official document (below) | Real |
| BoQ spreadsheets used for evaluation | **Synthetic**: built from the real HSPK values, with errors injected on purpose | Synthetic, labelled in every file |
| Why synthetic BoQs | A real BoQ has no answer key, so recall and precision cannot be measured on it. Injected errors give a ground truth | By design |

Numbers from the synthetic evaluation say how well each check detects *these* error types. They do not predict the error rate of a real project.

## Problem
Reviewing a RAB by hand is slow and error-prone: totals that do not add up, a decimal slip that makes concrete cost ten times too much, a unit changed from m2 to m3, the same line entered twice. A reviewer also needs a price benchmark, and the benchmark itself can be wrong.

## What it checks
| Check | What it catches | Needs reference? |
|---|---|---|
| `LINE_TOTAL_MISMATCH` | volume x unit price differs from the line total (rounding up to Rp 1 tolerated) | no |
| `SECTION_SUBTOTAL_MISMATCH`, `TOTAL_MISMATCH` | subtotals and total do not equal the sum of what is displayed | no |
| `PPN_MISMATCH`, `GRAND_TOTAL_MISMATCH` | VAT and grand total arithmetic (PPN rate is configurable) | no |
| `MISSING_VALUE` | blank, zero or negative volume or price | no |
| `DUPLICATE_ITEM` | same description, unit, volume and price twice | no |
| `UNIT_MISMATCH` | unit incompatible with the reference unit (m3 vs m2); synonyms such as `M3`, `m³`, `m'`/`m1` are fine | yes |
| `PRICE_HIGH` / `PRICE_LOW` | unit price above 1.30x or below 0.60x the HSPK (configurable; severity grows with distance) | yes |

Items with no confident reference match are listed as **not compared**, never guessed.

## Real finding: the official reference has errors too
Running the validator on the real HSPK excerpt (`python -m boqcheck.cli reference`) finds four genuine inconsistencies in the source document, which I confirmed by hand against the printed table:

| Item | What the document prints | Why it matters |
|---|---|---|
| Galian Tanah Cadas/Rabat | Headline HSPK 168,750, but its own printed labour total is 191,250 | Which of the two is right? |
| Pekerjaan Beton K-275 | Headline 1,286,882 equals labour + materials only; the three equipment lines (63,375) are left out | The price is understated by the equipment cost |
| Pondasi Beton Bertulang "(150 kg besi + Bekisting)" | Rebar coefficient is 15.75 kg, while the column item uses 157.5 kg | Looks like a decimal slip, about 10x too little steel |
| Batu Kali Belah 1 Pc : 4 Ps | Numerically identical to the 1 Pc : 3 Ps item | Coefficients probably copied |

So a checker that trusted the benchmark blindly would pass these errors on to every BoQ. When a BoQ line is compared against a reference item that has such an issue, the finding says so (`reference_data_issues` in the evidence).

## How it works
```
BoQ (xlsx/csv) --> parser --> deterministic checks (+ fuzzy item matcher vs HSPK) --> findings F001, F002 ...
                                                              |
                          LLM agent (read-only tools) <-------+   investigates, resolves ambiguous items,
                                  |                                writes the report in ID or EN
                                  v
                 report + automatic citation check (invented IDs, forgotten high-severity findings)
```
- **Code does the numbers.** Parsing, arithmetic, matching, thresholds and finding IDs are plain tested code.
- **The agent adds judgement.** Tools: `get_overview`, `list_findings`, `get_finding`, `get_boq_row`, `search_reference`, `get_reference_item`, `resolve_match`. It can resolve an ambiguous or unmatched line to a reference item (which re-runs the checks for that row), but it cannot edit the BoQ or invent a finding.
- **The report is audited.** Each cited ID must exist, and every high-severity finding should be mentioned; both are computed after each run.
- **Conservative matcher.** Text matching uses IDF-weighted tokens and penalises mismatched numeric specs (K-225 vs K-250, 1:4 vs 1:3, 1/2 bata vs 1 bata). It prefers "not matched" over a wrong match.

## Evaluation (synthetic BoQs, 50 files, 609 injected errors, seeded and reproducible)
```bash
python -m evaluation.run_eval --n 50       # no LLM, no network; writes evaluation/results/latest.md
```
| Check | Injected | Recall | False positives |
|---|---|---|---|
| Line total, subtotal, total, PPN, grand total, missing value, duplicate | 328 | 100% | 0 |
| UNIT_MISMATCH | 73 | 94.5% | 0 |
| PRICE_HIGH | 128 | 95.3% | 0 |
| PRICE_LOW | 80 | 92.5% | 0 |
| **Overall** | **609** | **97.4%** | **0 (precision 100%)** |

How to read this honestly:
- **Arithmetic checks are exact by construction**, so 100% there is expected, not impressive.
- **The 16 misses are all reference-based** and all come from the same cause: the matcher left 121 of 1,676 reference-backed lines unmatched (92.8% matched correctly, **0 matched wrongly**, and 0 of 252 custom or near-miss lines such as "Beton K-300" or "Keramik 60x60" were force-matched). Unmatched lines are exactly what the agent is for. With a *perfect* resolver the same checks reach 100% recall, so the upper bound on what the agent can add is about 2.6 points. **Its actual contribution is not measured here**; that needs a live model run.
- **Thresholds trade precision for recall.** In this generator, honest bids sit at 0.80-1.22x HSPK and errors at 1.35x and above or 0.58x and below. Real price spreads overlap far more, so expect lower precision at the same thresholds.

| High / low ratio | Precision | Recall (price checks only) |
|---|---|---|
| 1.15 / 0.85 | 36.0% | 94.2% |
| 1.30 / 0.60 (default) | 100% | 94.2% |
| 1.40 / 0.55 | 100% | 86.1% |
| 1.50 / 0.50 | 100% | 73.6% |
| 1.70 / 0.40 | 100% | 64.9% |

## Verified by running it (2 Nov 2026)

The claims above were reproduced from this checkout, on the real reference data:

- **36 of 36 unit tests pass** (`python -m unittest discover -s tests -t .`).
- **Reference audit reproduces exactly the four known issues.** `python -m boqcheck.cli reference` returns R001–R004 as documented in [`docs/reference_data_findings.md`](docs/reference_data_findings.md), and nothing else.
- **Evaluation reproduces byte-identically.** Re-running `python -m evaluation.run_eval --n 50` regenerates `evaluation/results/latest.md` with no differences: precision 100%, recall 97.4% (TP 593, FP 0, FN 16), item matcher 92.8% correct and 0 matched wrongly.
- **Sample BoQ:** `data/boq/sample_boq_synthetic.xlsx` carries 11 injected errors (see its truth CSV). The checker flags 10 of them with 0 false positives; the 11th is a deliberately misspelled "Beton K-200" line with no reference item, which it lists under *not compared* instead of guessing. Full output: [`docs/sample_check_report.md`](docs/sample_check_report.md).
- **Bug fixed in this pass:** `scripts/make_synthetic_boq.py` crashed with `ModuleNotFoundError` when run as a plain file; it now adds the project root to `sys.path` first. Generated BoQs from it check normally.
- The reference CSVs hold exactly what the README says: 38 items and 260 components transcribed from the Perbup.
- Still **not** verified: a live Anthropic agent run (needs an API key), as stated under Tests.

## Quick start
```bash
git clone https://github.com/andikapratamazaid/boq-cost-checker-agent.git
cd boq-cost-checker-agent
pip install -r requirements.txt

python -m boqcheck.cli check data/boq/sample_boq_synthetic.xlsx          # deterministic report, no API key
python -m boqcheck.cli check your_rab.xlsx --ppn 0.11 --out report.md   # your own sheet
python -m boqcheck.cli reference                                         # audit the reference data itself

export ANTHROPIC_API_KEY=...                                             # optional: LLM audit report
python -m boqcheck.cli check your_rab.xlsx --agent
```
**Your BoQ format:** a header row containing *Uraian*, *Satuan*, *Volume*, *Harga Satuan* and *Jumlah* (aliases accepted). Section titles, `Jumlah ...` subtotals, `TOTAL`, `PPN` and `TOTAL + PPN` rows are recognised (see the convention in `boqcheck/boq.py`).
**Your own prices:** replace the two CSVs in `data/reference/` with the HSPK/AHSP of your region and year, using the same columns.

## Tests
```bash
python -m unittest discover -s tests -t .
```
36 tests: number and unit parsing, xlsx/csv parsing, every check (including hard negatives such as rounding differences, unit synonyms and prices just inside the thresholds), the matcher and its near-miss refusals, the real-data validator (it must find exactly the four known issues and nothing else), the evaluation harness, the agent loop with a scripted fake LLM, and the CLI.

**What was not verified:** the live Anthropic API adapter (`boqcheck/llm.py`) and anything an actual model does with these tools (matching quality, report quality). Those need your own run. The agent loop itself is tested with a scripted stand-in.

## Limitations
- The reference is one regency's HSPK excerpt (38 items). Other regions, years and items need their own data. HSPK is a government budgeting benchmark and may differ from market prices; whether it includes tax, overhead and profit varies between documents, so the checker uses bands, not exact prices.
- The PPN rate is a configuration value (default 11% effective). Check the rule that applies to your contract and date.
- No quantity-reasonableness checks yet (for example rebar kg per m3 of concrete) and no drawing take-off.
- Finding messages are in English; the agent writes the final report in the user's language.
- A flag is a prompt for human review by a quantity surveyor, not a verdict.

## Next steps
- Add the full HSPK and AHSP (SNI) coefficient tables, plus several regions
- Quantity-ratio checks between related items
- Streamlit upload UI
- Measure the live agent: matching accuracy after resolution, citation validity, report quality (LLM-as-judge validated against human labels)

## Related projects
- [Text-to-SQL Analytics Agent](https://github.com/andikapratamazaid/text2sql-analytics-agent)
- [E-Commerce RFM & Cohort (SQL)](https://github.com/andikapratamazaid/ecommerce-rfm-cohort-sql)

## Author
**Andika Pratama Zaid** · [LinkedIn](https://linkedin.com/in/andikapratamazaid) · [GitHub](https://github.com/andikapratamazaid)
