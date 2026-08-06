"""Confidence function — formal-model.md §5."""
from __future__ import annotations
import math

TAU_DEFAULT = 2.0


def confidence(n_eff: int, tau: float = TAU_DEFAULT) -> float:
    """confidence(t) = 1 - exp(-n_eff / tau)"""
    if n_eff < 0:
        raise ValueError("n_eff must be >= 0")
    return 1.0 - math.exp(-n_eff / tau)
