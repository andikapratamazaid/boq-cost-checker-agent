# Reference data: HSPK excerpt (real)

**Source:** Peraturan Bupati Bengkulu Selatan No. 25 Tahun 2025, *Harga Satuan Pokok Kegiatan (HSPK) Tahun Anggaran 2026*.
The PDF was read from a public mirror (`https://jnnqvmfhkqwfdlzevfao.supabase.co/storage/v1/object/public/regulation-pdfs/perbup-kab-bengkulu-selatan-no-25-tahun-2025.pdf`).
Verify values against the official publication of Kabupaten Bengkulu Selatan before relying on them. As an official regional
regulation it is generally not covered by copyright in Indonesia (UU 28/2014, Art. 43), but check this yourself before redistributing.

## What is in the two CSV files
- `hspk_bengkulu_selatan_2026_items.csv`: 38 work items (unit price analyses): description, unit, headline HSPK (`nilai_hspk`), printed category totals, approximate page, and a `note` where the source is internally inconsistent.
- `hspk_bengkulu_selatan_2026_components.csv`: 260 component lines (labour, materials, equipment) with coefficient, unit, unit price and the amount **as printed** (`jumlah_printed`).

## How the excerpt was made
- Typical building-work items were hand-selected (earthwork, foundation, concrete, formwork, rebar, walls, plaster, paint, floor tile, roof, ceiling, glass, ironmongery). It is **not** the full price book.
- Numbers were transcribed from the PDF text: decimal commas became decimal points, thousand separators were removed, units normalised lightly (for example `0,6M3` became `M3`).
- Printed values were kept even when the source contradicts itself (see `note` and `docs/reference_data_findings.md`). A transcription cross-check (printed components vs printed totals) matched for 36 of 38 items; the two that do not are genuine source inconsistencies.
- Page numbers are approximate.

## Caveats
- One regency's prices. Other regions need their own HSPK; the loader accepts any CSV with the same columns.
- HSPK is a government budgeting benchmark. Whether it includes tax, overhead and profit differs between regions and documents; the checker therefore uses tolerance bands rather than treating it as an exact price.
