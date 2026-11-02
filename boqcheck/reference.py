"""Reference price data (HSPK) and validation of the reference itself."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .findings import Finding

DEFAULT_ITEMS = "data/reference/hspk_bengkulu_selatan_2026_items.csv"
DEFAULT_COMPONENTS = "data/reference/hspk_bengkulu_selatan_2026_components.csv"
DEFAULT_SOURCE = "Perbup Kab. Bengkulu Selatan No. 25/2025 (HSPK TA 2026)"


@dataclass
class Reference:
    items: pd.DataFrame
    components: pd.DataFrame
    source: str = DEFAULT_SOURCE

    def item(self, item_id: str) -> dict:
        r = self.items[self.items.item_id == item_id]
        return r.iloc[0].to_dict() if len(r) else {}

    def components_of(self, item_id: str) -> pd.DataFrame:
        return self.components[self.components.item_id == item_id]


def load_reference(items_csv: str = DEFAULT_ITEMS, components_csv: str = DEFAULT_COMPONENTS,
                   source: str = DEFAULT_SOURCE) -> Reference:
    for p in (items_csv, components_csv):
        if not Path(p).exists():
            raise FileNotFoundError(f"Reference file not found: {p}")
    items = pd.read_csv(items_csv)
    comps = pd.read_csv(components_csv)
    return Reference(items, comps, source)


def validate_reference(ref: Reference) -> list[Finding]:
    """Check the reference data itself. Official price books contain errors; a checker that
    trusts them blindly would pass those errors on to every BoQ it audits."""
    out: list[Finding] = []
    n = 0

    def add(check, sev, item_id, uraian, msg, expected=None, actual=None, evidence=None, action=""):
        nonlocal n
        n += 1
        out.append(Finding(f"R{n:03d}", "reference", check, sev, item_id, uraian, msg, expected, actual,
                           evidence or {}, action))

    for _, it in ref.items.iterrows():
        c = ref.components_of(it.item_id)
        total_components = float(c.jumlah_printed.sum())
        # 1. headline HSPK vs sum of all printed component amounts
        if abs(total_components - it.nilai_hspk) > max(100.0, 0.005 * it.nilai_hspk):
            diff = total_components - it.nilai_hspk
            alat_sum = float(c[c.kategori == "alat"].jumlah_printed.sum())
            ev = {"sum_of_components": total_components, "difference": diff}
            msg = (f"Printed HSPK ({it.nilai_hspk:,.0f}) differs from the sum of its printed components "
                   f"({total_components:,.0f}).")
            if alat_sum and abs(diff - alat_sum) <= 1:
                msg += " The difference equals the equipment total, so equipment looks excluded from the headline price."
                ev["equals_equipment_total"] = True
            add("HSPK_TOTAL_MISMATCH", "high", it.item_id, it.uraian, msg, it.nilai_hspk, total_components, ev,
                "Treat this reference price with caution; confirm with the source table.")
        # 2. coefficient x unit price vs printed amount
        for _, r in c.iterrows():
            calc = r.koefisien * r.harga_satuan
            if abs(calc - r.jumlah_printed) > max(5.0, 0.02 * abs(r.jumlah_printed)):
                add("COMPONENT_ARITHMETIC", "medium", it.item_id, it.uraian,
                    f"{r.komponen}: coefficient x price = {calc:,.0f} but printed amount is {r.jumlah_printed:,.0f}.",
                    calc, r.jumlah_printed, {"component": r.komponen})
        # 3. printed category totals
        for cat, col in (("upah", "upah_printed"), ("bahan", "bahan_printed"), ("alat", "alat_printed")):
            printed = it[col]
            if pd.notna(printed):
                s = float(c[c.kategori == cat].jumlah_printed.sum())
                if abs(s - printed) > 1:
                    add("CATEGORY_TOTAL_MISMATCH", "medium", it.item_id, it.uraian,
                        f"Printed {cat} total {printed:,.0f} differs from the sum of its lines {s:,.0f}.", printed, s)
        # 4. 'NNN kg besi' in the title vs rebar coefficient
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*kg\s*besi", it.uraian, flags=re.I)
        if m:
            label = float(m.group(1).replace(",", "."))
            rebar = c[(c.kategori == "bahan") & c.komponen.str.contains("besi beton", case=False)
                      & (c.satuan.str.lower() == "kg")]
            if len(rebar):
                coef = float(rebar.koefisien.sum())
                if abs(coef - label) / label > 0.20:
                    add("LABEL_COEFFICIENT_MISMATCH", "high", it.item_id, it.uraian,
                        f"Title states {label:g} kg of rebar but the rebar coefficient is {coef:g} kg"
                        + (" (about 10x smaller: possible decimal slip)." if 8 <= label / coef <= 12 else "."),
                        label, coef, {"ratio": label / coef},
                        "Confirm the coefficient in the source table before using this price.")

    # 5. different items with identical component sets and identical price
    sig = {}
    for _, it in ref.items.iterrows():
        c = ref.components_of(it.item_id)
        key = (float(it.nilai_hspk), tuple(sorted((r.komponen, round(float(r.koefisien), 4)) for _, r in c.iterrows())))
        sig.setdefault(key, []).append(it)
    for key, group in sig.items():
        if len(group) > 1:
            first = group[0]
            for dup in group[1:]:
                add("DUPLICATE_COMPONENTS", "medium", dup.item_id, dup.uraian,
                    f"Identical components and price as '{first.uraian}' ({first.item_id}) although the item description differs.",
                    evidence={"same_as": first.item_id},
                    action="Check whether the source table copied the wrong coefficients.")

    # 6. the same component priced differently in different items
    comps = ref.components.copy()
    comps["key"] = comps.komponen.str.lower().str.strip() + "|" + comps.satuan.str.lower().str.strip()
    for key, g in comps.groupby("key"):
        if g.harga_satuan.nunique() > 1:
            add("PRICE_INCONSISTENT_ACROSS_ITEMS", "medium", ",".join(sorted(set(g.item_id))[:5]), key.split("|")[0],
                f"Component '{key.split('|')[0]}' ({key.split('|')[1]}) has {g.harga_satuan.nunique()} different unit prices across items.",
                evidence={"prices": sorted(map(float, g.harga_satuan.unique()))})
    return out
