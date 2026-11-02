"""Generate SYNTHETIC BoQ spreadsheets with deliberately injected errors, plus the ground truth.

Why synthetic: a real BoQ comes with no answer key, so precision and recall cannot be measured on it.
Here the unit prices start from REAL HSPK reference values (data/reference), items are phrased in
varied ways, and every injected error is recorded, so detection can be scored.

The error rates, factors and the 'honest price band' below are modelling assumptions of this generator,
not measurements of real contractors. Results on this data show how well the checks work on these error
types; they do not predict the error rate or the mix of errors in a real project.

Usage:
  python scripts/make_synthetic_boq.py --out data/boq/synthetic --n 3
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np

if __package__ in (None, ""):  # allow running as a plain file: python scripts/make_synthetic_boq.py
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boqcheck.reference import load_reference

SECTIONS = [
    ("A. PEKERJAAN PERSIAPAN DAN TANAH", ["BS01", "BS02", "BS03", "BS04", "BS05"]),
    ("B. PEKERJAAN PONDASI", ["BS06", "BS07", "BS08", "BS09", "BS18"]),
    ("C. PEKERJAAN STRUKTUR BETON", ["BS10", "BS11", "BS12", "BS13", "BS14", "BS15", "BS16", "BS17", "BS19"]),
    ("D. PEKERJAAN DINDING DAN PLESTERAN", ["BS20", "BS21", "BS22", "BS23", "BS24", "BS25", "BS26", "BS27", "BS28"]),
    ("E. PEKERJAAN LANTAI DAN FINISHING", ["BS29", "BS30", "BS36", "BS37"]),
    ("F. PEKERJAAN ATAP DAN PLAFON", ["BS31", "BS32", "BS33", "BS34", "BS35", "BS38"]),
]
# Near-miss items that are NOT in the reference. A false match would create spurious findings.
CUSTOM_NEAR = [("Pekerjaan Beton K-300", "m3", 1500000), ("Pemasangan Dinding Batu Merah 1 Pc : 6 Pp tebal 1/2 bata", "m2", 125000),
               ("Pengecatan Tembok Lama", "m2", 38000), ("Pemasangan Keramik 60x60 cm", "m2", 280000),
               ("Pekerjaan Bekisting Plat Lantai", "m2", 230000), ("Pemasangan Kaca Tebal 8 mm", "m2", 520000),
               ("Pekerjaan Pembesian Wiremesh", "Kg", 26000), ("Pemasangan Plafon Gypsum Board", "m2", 190000)]
CUSTOM = [("Mobilisasi dan demobilisasi", "ls"), ("Pembersihan akhir lokasi", "ls"), ("Papan nama proyek", "bh"),
          ("Pekerjaan pagar besi tempa", "m1"), ("Instalasi titik lampu", "titik"), ("Sanitair kloset duduk", "unit")]
UNIT_VARIANTS = {"m1": ["m1", "m'", "m", "M1"], "m2": ["m2", "M2", "m²"], "m3": ["m3", "M3", "m³"],
                 "kg": ["kg", "Kg"], "buah": ["buah", "bh", "Buah"]}
WRONG_UNIT = {"m1": "m2", "m2": "m3", "m3": "m2", "kg": "m3", "buah": "m2"}
VOL_RANGE = {"m1": (30, 200), "m2": (40, 900), "m3": (4, 120), "kg": (500, 20000), "buah": (3, 40)}

HONEST_BAND = (0.80, 1.22)       # honest unit price / HSPK (bidders vary; HSPK is a benchmark)
HIGH_ERR = (1.35, 3.5)
LOW_ERR_GROSS, LOW_ERR_SUBTLE = (0.15, 0.40), (0.45, 0.58)


def paraphrase(u: str, rng) -> str:
    s = u
    def maybe(p=0.5):
        return rng.random() < p
    if maybe():
        s = re.sub(r"\bPekerjaan\b", "Pek.", s)
    if maybe():
        s = re.sub(r"\bPemasangan\b", str(rng.choice(["Pasangan", "Pas.", "Pemasangan"])), s)
    if maybe():
        s = s.replace("Batu Merah", "Bata Merah")
    if maybe(0.3):
        s = s.replace("tebal", "tbl")
    if maybe(0.4):
        s = s.replace("Bekisting", "Begisting")
    if maybe(0.4):
        s = s.replace("Pembesian", "Penulangan")
    if maybe(0.4):
        s = s.replace("Plesteran Halus", "Plesteran")
    s = re.sub(r"K-(\d+)", lambda m: str(rng.choice([f"K-{m.group(1)}", f"K{m.group(1)}", f"K {m.group(1)}"])), s)
    s = re.sub(r"1 Pc : (\d) (Ps|Pp)",
               lambda m: str(rng.choice([f"1 Pc : {m.group(1)} {m.group(2)}", f"1Pc:{m.group(1)}{m.group(2)}", f"1:{m.group(1)}"])), s)
    if maybe(0.15):
        for drop in (" (UITZET)", " untuk Konstruksi", " Motif", " Kelas 1"):
            s = s.replace(drop, "")
    c = rng.random()
    return s.upper() if c < 0.15 else (s.lower() if c < 0.30 else s)


def noisy(u: str, rng) -> str:
    """Typos and dropped words, the kind of noise found in real spreadsheets (numbers are left intact)."""
    words = u.split()
    if rng.random() < 0.25:
        cand = [i for i, w in enumerate(words) if len(w) >= 6 and w.isalpha()]
        if cand:
            i = cand[int(rng.integers(0, len(cand)))]; j = int(rng.integers(1, len(words[i]) - 2))
            w = words[i]; words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    if rng.random() < 0.2 and len(words) > 3:
        cand = [i for i, w in enumerate(words) if len(w) >= 4 and w.isalpha()]
        if cand:
            words.pop(cand[int(rng.integers(0, len(cand)))])
    return " ".join(words)


def swap_digits(n: int, rng) -> int:
    d = list(str(n))
    if len(d) < 3:
        return n * 10
    i = int(rng.integers(0, len(d) - 1))
    d[i], d[i + 1] = d[i + 1], d[i]
    out = int("".join(d))
    return out if out != n else n * 10


def build(seed: int, ref=None) -> dict:
    ref = ref or load_reference()
    rng = np.random.default_rng(seed)
    hs = {r.item_id: r for _, r in ref.items.iterrows()}

    lines = []                                  # one dict per BoQ line
    for si, (_, ids) in enumerate(SECTIONS):
        chosen = [i for i in ids if rng.random() < 0.85] or ids[:2]
        for iid in chosen:
            it = hs[iid]
            unit = it.satuan.lower()
            lo, hi = VOL_RANGE.get(unit, (5, 100))
            vol = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), 2)
            price = int(round(float(it.nilai_hspk) * rng.uniform(*HONEST_BAND)))
            lines.append(dict(sec=si, ref=iid, text=noisy(paraphrase(it.uraian, rng), rng), unit=str(rng.choice(UNIT_VARIANTS.get(unit, [it.satuan]))),
                              unit_key=unit, vol=vol, price=price, hspk=float(it.nilai_hspk), tags=[]))
    for name, unit in rng.permutation(np.array(CUSTOM, dtype=object))[: int(rng.integers(2, 4))]:
        lines.append(dict(sec=int(rng.integers(0, len(SECTIONS))), ref=None, text=str(name), unit=str(unit), unit_key=str(unit),
                          vol=float(rng.integers(1, 30)), price=int(rng.integers(150, 5000)) * 1000, hspk=None, tags=[]))
    for name, unit, price in [CUSTOM_NEAR[i] for i in rng.permutation(len(CUSTOM_NEAR))[: int(rng.integers(2, 4))]]:
        lines.append(dict(sec=int(rng.integers(0, len(SECTIONS))), ref=None, text=name, unit=unit, unit_key=unit.lower(),
                          vol=round(float(rng.uniform(10, 300)), 2), price=int(price * rng.uniform(0.9, 1.15)), hspk=None, tags=[]))
    for ln in lines:
        ln["jumlah"] = int(round(ln["vol"] * ln["price"]))
        ln["jumlah_disp"] = ln["jumlah"]
        ln["vol_disp"] = ln["vol"]
        ln["price_disp"] = ln["price"]
        ln["unit_disp"] = ln["unit"]
    lines.sort(key=lambda l: l["sec"])
    ref_idx = [i for i, l in enumerate(lines) if l["ref"]]

    def pick(k):
        k = min(k, len(pool))
        got = [pool.pop(int(rng.integers(0, len(pool)))) for _ in range(k)]
        return got
    pool = list(ref_idx)

    # --- inject line-level errors on distinct lines --------------------------------------------------
    for i in pick(int(rng.integers(2, 4))):                       # LINE_TOTAL_MISMATCH
        l = lines[i]; kind = rng.random()
        if kind < 0.35:
            l["jumlah_disp"] = int(round(l["jumlah"] * rng.uniform(1.08, 1.6))); tier = "gross"
        elif kind < 0.6:
            l["jumlah_disp"] = swap_digits(l["jumlah"], rng); tier = "gross"
        elif kind < 0.8:
            l["jumlah_disp"] = l["jumlah"] * 10; tier = "gross"
        else:
            l["jumlah_disp"] = l["jumlah"] + int(rng.integers(2, 4000)); tier = "subtle"
        l["tags"].append(("LINE_TOTAL_MISMATCH", tier))
    for i in pick(int(rng.integers(2, 4))):                       # PRICE_HIGH
        l = lines[i]; r = rng.random()
        if r < 0.2:
            p = l["price"] * 10; tier = "gross"                   # decimal slip
        else:
            f = rng.uniform(*HIGH_ERR); p = int(round(l["hspk"] * f)); tier = "gross" if f >= 1.6 else "subtle"
        l["price_disp"] = p; l["jumlah"] = l["jumlah_disp"] = int(round(l["vol"] * p)); l["tags"].append(("PRICE_HIGH", tier))
    for i in pick(int(rng.integers(1, 3))):                       # PRICE_LOW
        l = lines[i]; gross = rng.random() < 0.5
        f = rng.uniform(*(LOW_ERR_GROSS if gross else LOW_ERR_SUBTLE)); p = int(round(l["hspk"] * f))
        l["price_disp"] = p; l["jumlah"] = l["jumlah_disp"] = int(round(l["vol"] * p)); l["tags"].append(("PRICE_LOW", "gross" if gross else "subtle"))
    for i in pick(int(rng.integers(1, 3))):                       # UNIT_MISMATCH
        l = lines[i]; l["unit_disp"] = WRONG_UNIT.get(l["unit_key"], "m2"); l["tags"].append(("UNIT_MISMATCH", "gross"))
    for i in pick(1):                                             # MISSING_VALUE
        l = lines[i]; l["vol_disp"] = None if rng.random() < 0.5 else 0.0; l["tags"].append(("MISSING_VALUE", "gross"))
    dup_src = pick(int(rng.integers(1, 3)))                       # DUPLICATE_ITEM (copy of a clean line)
    dups = []
    for i in dup_src:
        c = dict(lines[i]); c["tags"] = [("DUPLICATE_ITEM", "gross")]; dups.append((i, c))
    for i, c in sorted(dups, key=lambda x: -x[0]):
        lines.insert(i + 1, c)

    # --- layout ------------------------------------------------------------------------------------------
    sub_err_sec = int(rng.integers(0, len(SECTIONS))) if rng.random() < 0.6 else None
    sheet = [["DAFTAR KUANTITAS DAN HARGA (SYNTHETIC TEST DATA)", "", "", "", "", ""],
             ["Pekerjaan: Pembangunan Gedung (contoh)", "", "", "", "", ""],
             ["", "", "", "", "", ""],
             ["No", "Uraian Pekerjaan", "Satuan", "Volume", "Harga Satuan (Rp)", "Jumlah Harga (Rp)"]]
    truth, match_truth = [], {}
    def emit(row, tags=()):
        sheet.append(row)
        rid = len(sheet)
        for chk, tier in tags:
            truth.append(dict(row_id=rid, check=chk, tier=tier))
        return rid
    sub_displayed = []
    for si, (title, _) in enumerate(SECTIONS):
        sec_lines = [l for l in lines if l["sec"] == si]
        if not sec_lines:
            continue
        emit(["", title, "", "", "", ""])
        s_disp = 0
        for k, l in enumerate(sec_lines, 1):
            rid = emit([k, l["text"], l["unit_disp"], l["vol_disp"], l["price_disp"], l["jumlah_disp"]], l["tags"])
            s_disp += l["jumlah_disp"]
            if l["ref"]:
                match_truth[rid] = l["ref"]
        shown = s_disp
        tags = []
        if sub_err_sec == si:
            shown = int(round(s_disp * rng.uniform(0.9, 1.1)))
            if abs(shown - s_disp) < 5:
                shown = s_disp + 1000
            tags = [("SECTION_SUBTOTAL_MISMATCH", "gross")]
        emit(["", f"Jumlah {title}", "", "", "", shown], tags)
        sub_displayed.append(shown)
        sheet.append(["", "", "", "", "", ""])
    total_true = sum(sub_displayed)
    total = total_true; t_tags = []
    if rng.random() < 0.3:
        total = int(round(total_true * rng.uniform(0.97, 1.03)));
        if abs(total - total_true) < 5: total = total_true + 5000
        t_tags = [("TOTAL_MISMATCH", "gross")]
    emit(["", "TOTAL (sebelum PPN)", "", "", "", total], t_tags)
    ppn = int(round(total * 0.11)); p_tags = []
    if rng.random() < 0.5:
        ppn = int(round(total * rng.choice([0.12, 0.10, 0.121]))); p_tags = [("PPN_MISMATCH", "gross")]
    emit(["", "PPN 11%", "", "", "", ppn], p_tags)
    grand = total + ppn; g_tags = []
    if rng.random() < 0.25:
        grand = grand + int(rng.integers(1, 9)) * 10000; g_tags = [("GRAND_TOTAL_MISMATCH", "gross")]
    emit(["", "TOTAL + PPN", "", "", "", grand], g_tags)
    return dict(seed=seed, sheet=sheet, truth=truth, match_truth=match_truth)


def write_boq(data: dict, xlsx_path: str | None = None, csv_path: str | None = None) -> None:
    if xlsx_path:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "RAB"
        for r in data["sheet"]:
            ws.append([None if v == "" or v is None else v for v in r])
        ws.column_dimensions["B"].width = 60
        wb.save(xlsx_path)
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for r in data["sheet"]:
                w.writerow(["" if v is None else v for v in r])


def write_truth(data: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["row_id", "check", "tier"])
        for t in data["truth"]:
            w.writerow([t["row_id"], t["check"], t["tier"]])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/boq/synthetic")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ref = load_reference()
    for s in range(a.n):
        d = build(s, ref)
        write_boq(d, str(out / f"boq_{s:03d}.xlsx"), str(out / f"boq_{s:03d}.csv"))
        write_truth(d, str(out / f"boq_{s:03d}_truth.csv"))
        print(f"seed {s}: {len(d['sheet'])} rows, {len(d['truth'])} injected errors")
