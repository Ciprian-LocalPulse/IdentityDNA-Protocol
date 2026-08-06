"""
Trust Score — formal-model.md §3, the central computation of the Trust
Engine. Implements:

    TS = clamp( w1*S_identity + w2*S_history + w3*S_context - w4*R_risk, 0, 100 )
"""
from __future__ import annotations

import sys
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from weights import TrustWeights, DEFAULT_WEIGHTS  # noqa: E402
from confidence import confidence  # noqa: E402
from rules import evaluate_risk, DEFAULT_RULES  # noqa: E402
from history import TrustHistory  # noqa: E402
from policies import TrustPolicy, DEFAULT_POLICY, Decision  # noqa: E402


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class TrustResult:
    trust_score: float
    decision: Decision
    risk_flags: list[str]
    components: dict[str, float]


def compute_identity_score(distance: float | None, conf: float) -> float:
    """formal-model.md §3.2: S_identity = 100*(1 - d/2) * confidence.

    Range: [0, 100*conf]. d=0 (perfect match) -> 100*conf (maximum).
    d=1 (orthogonal / no information) -> 50*conf (neutral midpoint).
    d=2 (maximally divergent) -> 0.

    If distance is None (no baseline yet - first session for this
    subject), formal-model.md §3.2.1 mandates treating it as the neutral
    midpoint d=1, NOT as either a perfect match or a mismatch -- a first
    session is genuinely uninformative about identity consistency."""
    d = 1.0 if distance is None else distance
    return 100.0 * (1.0 - d / 2.0) * conf


def compute_context_score(context_priors: list[float]) -> float:
    """formal-model.md §3.5: S_context = 100 * product(p_j)."""
    if not context_priors:
        return 100.0
    product = 1.0
    for p in context_priors:
        product *= clamp(p, 0.0, 1.0)
    return 100.0 * product


def compute_trust_score(
    *,
    identity_distance: float | None,
    n_eff: int,
    subject_id: str,
    history: TrustHistory,
    context_priors: list[float],
    risk_context: dict[str, Any],
    weights: TrustWeights = DEFAULT_WEIGHTS,
    policy: TrustPolicy = DEFAULT_POLICY,
) -> TrustResult:
    weights.validate()

    conf = confidence(n_eff)
    s_identity = compute_identity_score(identity_distance, conf)
    s_history = history.score(subject_id)
    s_context = compute_context_score(context_priors)
    r_risk, risk_flags = evaluate_risk(risk_context)

    ts = clamp(
        weights.w_identity * s_identity
        + weights.w_history * s_history
        + weights.w_context * s_context
        - weights.w_risk * r_risk,
        0.0,
        100.0,
    )

    decision = policy.decide(ts)

    return TrustResult(
        trust_score=round(ts, 2),
        decision=decision,
        risk_flags=risk_flags,
        components={
            "S_identity": round(s_identity, 2),
            "S_history": round(s_history, 2),
            "S_context": round(s_context, 2),
            "R_risk": round(r_risk, 2),
            "confidence": round(conf, 4),
        },
    )
