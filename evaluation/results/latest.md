# Detection evaluation (synthetic BoQs with injected errors)

- BoQs: 50 | item lines: 1928 | injected errors: 609
- Thresholds: price high > 1.3x HSPK, low < 0.6x; PPN 11%; line tolerance Rp 1

**Overall: precision 100.0%, recall 97.4%, F1 98.7%** (TP 593, FP 0, FN 16)

| Check | Injected | Detected | Recall | False positives | Precision |
|---|---|---|---|---|---|
| LINE_TOTAL_MISMATCH | 125 | 125 | 100.0% | 0 | 100.0% |
| PRICE_HIGH | 128 | 122 | 95.3% | 0 | 100.0% |
| PRICE_LOW | 80 | 74 | 92.5% | 0 | 100.0% |
| UNIT_MISMATCH | 73 | 69 | 94.5% | 0 | 100.0% |
| MISSING_VALUE | 50 | 50 | 100.0% | 0 | 100.0% |
| DUPLICATE_ITEM | 73 | 73 | 100.0% | 0 | 100.0% |
| SECTION_SUBTOTAL_MISMATCH | 30 | 30 | 100.0% | 0 | 100.0% |
| TOTAL_MISMATCH | 16 | 16 | 100.0% | 0 | 100.0% |
| PPN_MISMATCH | 28 | 28 | 100.0% | 0 | 100.0% |
| GRAND_TOTAL_MISMATCH | 6 | 6 | 100.0% | 0 | 100.0% |

**Upper bound with a perfect item resolver** (every reference-backed line matched correctly, which is the job left to the agent): precision 100.0%, recall 100.0%. The gap between the two recall figures is the headroom the agent can add; it is not measured here because that needs a live model.

## Recall by error tier

| Check | Tier | Detected / Injected |
|---|---|---|
| DUPLICATE_ITEM | gross | 73 / 73 |
| GRAND_TOTAL_MISMATCH | gross | 6 / 6 |
| LINE_TOTAL_MISMATCH | gross | 101 / 101 |
| LINE_TOTAL_MISMATCH | subtle | 24 / 24 |
| MISSING_VALUE | gross | 50 / 50 |
| PPN_MISMATCH | gross | 28 / 28 |
| PRICE_HIGH | gross | 108 / 114 |
| PRICE_HIGH | subtle | 14 / 14 |
| PRICE_LOW | gross | 32 / 35 |
| PRICE_LOW | subtle | 42 / 45 |
| SECTION_SUBTOTAL_MISMATCH | gross | 30 / 30 |
| TOTAL_MISMATCH | gross | 16 / 16 |
| UNIT_MISMATCH | gross | 69 / 73 |

## Item matching (BoQ text -> reference item)

- Reference-backed lines: 1676 | correct: 1555 (92.8%) | wrong: 0 | not matched (left for the agent): 121
- Custom lines with no reference item: 252 | wrongly matched: 0

## Price threshold sweep (PRICE_HIGH / PRICE_LOW only)

| high ratio | low ratio | precision | recall |
|---|---|---|---|
| 1.15 | 0.85 | 36.0% | 94.2% |
| 1.22 | 0.78 | 100.0% | 94.2% |
| 1.3 | 0.6 | 100.0% | 94.2% |
| 1.4 | 0.55 | 100.0% | 86.1% |
| 1.5 | 0.5 | 100.0% | 73.6% |
| 1.7 | 0.4 | 100.0% | 64.9% |

## False positives (first 15)

None.

> The honest-price band (0.80-1.22x HSPK) and the error factors are generator assumptions. Precision and recall here describe these error types only, not real-project error rates.
