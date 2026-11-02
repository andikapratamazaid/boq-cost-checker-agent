# BoQ check: data/boq/sample_boq_synthetic.xlsx

Reference prices: Perbup Kab. Bengkulu Selatan No. 25/2025 (HSPK TA 2026). HSPK is a regional price ceiling/benchmark, not an auditor's verdict; every flag is a prompt for human review.

**10 issue(s) flagged**, 6 item(s) not compared with the reference.

| Check | Count |
|---|---|
| LINE_TOTAL_MISMATCH | 2 |
| PRICE_HIGH | 2 |
| UNIT_MISMATCH | 2 |
| MISSING_VALUE | 1 |
| DUPLICATE_ITEM | 1 |
| PPN_MISMATCH | 1 |
| PRICE_LOW | 1 |

## Findings

| ID | Severity | Check | Row | Item | Detail |
|---|---|---|---|---|---|
| F007 | high | PRICE_HIGH | 14 | Pekerjaan Pas. Batu Kali Belah 15/20 cm (1Pc:4Ps | Unit price 3,838,010 is 3.37x the reference HSPK 1,137,300. |
| F009 | high | PRICE_HIGH | 24 | Pek. Bekisting Sloof | Unit price 2,313,990 is 10.43x the reference HSPK 221,880. |
| F010 | high | UNIT_MISMATCH | 30 | Pemasangan Dinding Batu Merah 1Pc:3Pp tebal 1/2  | Unit 'm3' does not match the reference unit 'm2' for 'Pemasangan Dinding Batu Merah 1 Pc : 3 Pp tebal 1/2 bata'. |
| F015 | high | UNIT_MISMATCH | 54 | Pemasangan Kuda-Kuda Kayu Jati (Bentang Max.6 me | Unit 'm2' does not match the reference unit 'm3' for 'Pemasangan Kuda-Kuda Kayu Jati (Bentang Max.6 meter)'. |
| F003 | high | MISSING_VALUE | 56 | pek. pemasangan prfoil | Volume is missing, zero or negative. |
| F005 | high | PPN_MISMATCH | 60 | PPN 11% | PPN at 11% of the displayed total is 447,881,809 but the sheet shows 407,165,281. |
| F006 | high | PRICE_LOW | 8 | Galian Tanah Cadas/Rabat | Unit price 45,689 is only 0.27x the reference HSPK 168,750. |
| F004 | medium | DUPLICATE_ITEM | 32 | pasangan dinding bata merah 1:4 tebal 1/2 bata | Same description, unit, volume and price as row 31: possible double counting. |
| F001 | medium | LINE_TOTAL_MISMATCH | 34 | PEMASANGAN DINDING BATU MERAH 1PC:4PP TBL 1 BATA | Volume x unit price = 123,901,891 but the line total is 123,904,154. |
| F002 | medium | LINE_TOTAL_MISMATCH | 35 | Plesteran Halus 1Pc:3Ps tebal 1.5 cm | Volume x unit price = 12,755,778 but the line total is 12,575,778. |

## Not compared (no confident reference match)

- row 20: Pekejraan Beton K-200
- row 40: Mobilisasi dan demobilisasi
- row 41: Pemasangan Dinding Batu Merah 1 Pc : 6 Pp tebal 1/2 bata
- row 42: Pekerjaan Beton K-300
- row 49: Sanitair kloset duduk
- row 56: pek. pemasangan prfoil
