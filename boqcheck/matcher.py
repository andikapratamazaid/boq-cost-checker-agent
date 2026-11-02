"""Match a BoQ item description to a reference (HSPK) item.

Score = IDF-weighted Jaccard overlap of normalised tokens, reduced when numeric tokens disagree
(K-225 vs K-250, 1:4 vs 1:3, 1/2 bata vs 1 bata). The unit is deliberately NOT used, so an item with a
wrong unit can still be matched and then reported as a unit mismatch.
An ambiguous or weak match is reported as such rather than guessed; the agent can resolve those.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .findings import Config
from .reference import Reference
from .util import has_digit, norm_text


@dataclass
class MatchResult:
    candidates: list[tuple[str, float]] = field(default_factory=list)   # (item_id, score), best first
    item_id: str | None = None                                          # set only when accepted
    status: str = "unmatched"                                           # matched | ambiguous | unmatched

    @property
    def best_score(self) -> float:
        return self.candidates[0][1] if self.candidates else 0.0


class FuzzyMatcher:
    def __init__(self, ref: Reference, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.tokens = {r.item_id: set(norm_text(r.uraian)) for _, r in ref.items.iterrows()}
        df: dict[str, int] = {}
        for ts in self.tokens.values():
            for t in ts:
                df[t] = df.get(t, 0) + 1
        n = len(self.tokens)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self.default_idf = math.log(n + 1) + 1.0

    def _w(self, t: str) -> float:
        return self.idf.get(t, self.default_idf)

    def score(self, text_tokens: set[str], ref_tokens: set[str]) -> float:
        inter = sum(self._w(t) for t in text_tokens & ref_tokens)
        union = sum(self._w(t) for t in text_tokens | ref_tokens)
        base = inter / union if union else 0.0
        a = {t for t in text_tokens if has_digit(t)}
        b = {t for t in ref_tokens if has_digit(t)}
        mism = len(a ^ b)
        return base * (0.6 ** min(mism, 3))

    def candidates(self, text: str, k: int = 5) -> list[tuple[str, float]]:
        tt = set(norm_text(text))
        scored = sorted(((i, self.score(tt, rt)) for i, rt in self.tokens.items()), key=lambda x: -x[1])
        return [(i, round(s, 4)) for i, s in scored[:k]]

    def match(self, text: str) -> MatchResult:
        cands = self.candidates(text)
        if not cands or cands[0][1] < self.cfg.match_min_score:
            return MatchResult(cands, None, "unmatched")
        margin = cands[0][1] - (cands[1][1] if len(cands) > 1 else 0.0)
        if margin < self.cfg.match_min_margin:
            return MatchResult(cands, None, "ambiguous")
        return MatchResult(cands, cands[0][0], "matched")
