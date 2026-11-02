from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Config:
    ppn_rate: float = 0.11            # effective VAT rate used for the PPN check (verify the current rule)
    line_tol_rp: float = 1.0          # rounding tolerance for volume x unit price vs line total (rupiah)
    sum_tol_rp: float = 1.0           # tolerance for subtotal / total / PPN / grand-total arithmetic
    price_high_ratio: float = 1.30    # BoQ unit price / HSPK above this is flagged
    price_low_ratio: float = 0.60     # BoQ unit price / HSPK below this is flagged
    high_severity_ratio: float = 1.60
    low_severity_ratio: float = 0.40
    match_min_score: float = 0.50     # minimum text-match score to trust a reference match
    match_min_margin: float = 0.05    # minimum gap between best and second-best candidate


@dataclass
class Finding:
    finding_id: str
    scope: str                 # 'boq' | 'reference'
    check: str
    severity: str              # high | medium | low | info
    row: object                # BoQ sheet row number, or reference item_id
    item: str
    message: str
    expected: float | None = None
    actual: float | None = None
    evidence: dict = field(default_factory=dict)
    action: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
