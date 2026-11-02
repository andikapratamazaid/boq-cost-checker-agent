# Reference data validation

Reference prices: Perbup Kab. Bengkulu Selatan No. 25/2025 (HSPK TA 2026). HSPK is a regional price ceiling/benchmark, not an auditor's verdict; every flag is a prompt for human review.

**4 issue(s) flagged**, 0 item(s) not compared with the reference.

| Check | Count |
|---|---|
| HSPK_TOTAL_MISMATCH | 2 |
| LABEL_COEFFICIENT_MISMATCH | 1 |
| DUPLICATE_COMPONENTS | 1 |

## Findings

| ID | Severity | Check | Row | Item | Detail |
|---|---|---|---|---|---|
| R001 | high | HSPK_TOTAL_MISMATCH | BS03 | Galian Tanah Cadas/Rabat | Printed HSPK (168,750) differs from the sum of its printed components (191,250). |
| R002 | high | HSPK_TOTAL_MISMATCH | BS14 | Pekerjaan Beton K-275 | Printed HSPK (1,286,882) differs from the sum of its printed components (1,350,257). The difference equals the equipment total, so equipment looks excluded from the headline price. |
| R003 | high | LABEL_COEFFICIENT_MISMATCH | BS18 | Pekerjaan Pondasi Beton Bertulang (150 kg besi + | Title states 150 kg of rebar but the rebar coefficient is 15.75 kg (about 10x smaller: possible decimal slip). |
| R004 | medium | DUPLICATE_COMPONENTS | BS07 | Pekerjaan Pemasangan Batu Kali Belah 15/20 cm (1 | Identical components and price as 'Pekerjaan Pemasangan Batu Kali Belah 15/20 cm (1 Pc : 3 Ps)' (BS06) although the item description differs. |

