import pandas as pd

from boqcheck.boq import BoQ


def make_boq(rows):
    """rows: (kind, uraian, satuan, volume, harga_satuan, jumlah[, section]) -> BoQ with sequential row ids from 5."""
    recs, section = [], ""
    for i, r in enumerate(rows):
        kind, uraian, sat, vol, hs, jm = r[:6]
        section = r[6] if len(r) > 6 else (uraian if kind == "section" else section)
        recs.append(dict(row_id=i + 5, kind=kind, no="", uraian=uraian, satuan=sat, volume=vol, harga_satuan=hs,
                         jumlah=jm, section=section))
    return BoQ(pd.DataFrame(recs))
