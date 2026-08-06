"""Trust Engine weights — formal-model.md §3.1 defaults, policy-overridable."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class TrustWeights:
    w_identity: float = 0.35
    w_history: float = 0.30
    w_context: float = 0.15
    w_risk: float = 0.20

    def validate(self) -> None:
        """Sanity bounds only. formal-model.md §3.1 does NOT require
        w_identity + w_history + w_context to sum to 1 — TS is a weighted
        composite with risk subtracted separately, not a convex
        combination, so weights may sum to any positive value as long as
        the clamp(0,100) in compute_trust_score keeps TS in range."""
        for name, w in (("w_identity", self.w_identity), ("w_history", self.w_history),
                         ("w_context", self.w_context), ("w_risk", self.w_risk)):
            if w < 0:
                raise ValueError(f"{name} must be >= 0")


DEFAULT_WEIGHTS = TrustWeights()
