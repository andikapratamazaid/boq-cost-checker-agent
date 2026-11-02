"""Read a BoQ / RAB spreadsheet (xlsx or csv) into a structured table.

Row classification convention (documented because real sheets vary):
  section   : a description with no volume, unit price or amount
  item      : a row with a volume, unit price or amount
  subtotal  : description starts with 'Jumlah' / 'Sub total'
  total     : description starts with 'Total' / 'Jumlah total' (before tax)
  ppn       : description starts with 'PPN'
  grand     : 'Total + PPN', 'Jumlah termasuk PPN', 'Grand total', 'Dibulatkan'
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .util import parse_number

ALIASES = {
    "no": ["no", "no.", "nomor"],
    "uraian": ["uraian", "uraian pekerjaan", "jenis pekerjaan", "item pekerjaan", "deskripsi"],
    "satuan": ["satuan", "sat", "sat."],
    "volume": ["volume", "vol", "vol.", "kuantitas", "qty"],
    "harga_satuan": ["harga satuan", "harga satuan (rp)", "harga sat", "harga satuan (rp.)", "hs"],
    "jumlah": ["jumlah harga", "jumlah harga (rp)", "jumlah", "total harga", "jumlah (rp)", "harga total"],
}

_PPN = re.compile(r"^\s*(ppn|pajak pertambahan nilai)\b", re.I)
_GRAND = re.compile(r"(grand\s*total|(total|jumlah)\s*(\(?harga\)?)?\s*(\+|termasuk|dengan|incl\w*)\s*ppn|dibulatkan)", re.I)
_TOTAL = re.compile(r"^\s*(total|jumlah\s*total|jumlah\s*seluruh|jumlah\s*keseluruhan)\b", re.I)
_SUB = re.compile(r"^\s*(jumlah|sub\s*-?\s*total|subtotal)\b", re.I)


@dataclass
class BoQ:
    rows: pd.DataFrame      # row_id, kind, no, uraian, satuan, volume, harga_satuan, jumlah, section

    @property
    def items(self) -> pd.DataFrame:
        return self.rows[self.rows.kind == "item"]

    def recap(self, kind: str):
        r = self.rows[self.rows.kind == kind]
        return r.iloc[-1] if len(r) else None


def _norm_header(h) -> str:
    return re.sub(r"\s+", " ", str(h or "").strip().lower())


def _find_header(raw: pd.DataFrame) -> tuple[int, dict]:
    for i in range(min(len(raw), 40)):
        cells = [_norm_header(v) for v in raw.iloc[i].tolist()]
        cols = {}
        for key, names in ALIASES.items():
            for j, c in enumerate(cells):
                if c in names and key not in cols:
                    cols[key] = j
        if {"uraian", "volume", "harga_satuan", "jumlah"} <= cols.keys():
            return i, cols
    raise ValueError("Could not find a header row with Uraian / Volume / Harga Satuan / Jumlah columns.")


def load_boq(path: str, sheet=0, locale: str = "auto") -> BoQ:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        raw = pd.read_excel(p, sheet_name=sheet, header=None, dtype=object)
    else:
        raw = pd.read_csv(p, header=None, dtype=object, skip_blank_lines=False, keep_default_na=False)
    hdr, cols = _find_header(raw)

    recs, section = [], ""
    for i in range(hdr + 1, len(raw)):
        row = raw.iloc[i]
        get = lambda k: row.iloc[cols[k]] if k in cols else None
        uraian = str(get("uraian") or "").strip()
        uraian = "" if uraian.lower() == "nan" else uraian
        vol, hs, jm = (parse_number(get(k), locale) for k in ("volume", "harga_satuan", "jumlah"))
        sat = str(get("satuan") or "").strip()
        sat = "" if sat.lower() == "nan" else sat
        no = get("no")
        no = "" if no is None or str(no).lower() == "nan" else str(no).strip()
        if not uraian and vol is None and hs is None and jm is None:
            continue
        if _GRAND.search(uraian):
            kind = "grand"
        elif _PPN.search(uraian):
            kind = "ppn"
        elif _TOTAL.search(uraian):
            kind = "total"
        elif _SUB.search(uraian):
            kind = "subtotal"
        elif vol is None and hs is None and jm is None:
            kind = "section"
            section = uraian
        else:
            kind = "item"
        recs.append(dict(row_id=i + 1, kind=kind, no=no, uraian=uraian, satuan=sat, volume=vol,
                         harga_satuan=hs, jumlah=jm, section=section))
    return BoQ(pd.DataFrame(recs))
