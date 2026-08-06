"""
Policies — RFC-0001 §8.4 decision thresholds. Relying Parties can
override per resource sensitivity (RFC-0001 §8, final paragraph).
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    STEP_UP = "STEP_UP"
    DENY = "DENY"


@dataclass(frozen=True)
class TrustPolicy:
    allow_threshold: float = 80.0
    step_up_threshold: float = 50.0
    name: str = "default"

    def decide(self, trust_score: float) -> Decision:
        if trust_score >= self.allow_threshold:
            return Decision.ALLOW
        if trust_score >= self.step_up_threshold:
            return Decision.STEP_UP
        return Decision.DENY


DEFAULT_POLICY = TrustPolicy()

# Example of a stricter policy for high-value resources (threat-model.md §3.4
# recommends shorter rotation + here, a higher bar for ALLOW).
HIGH_SENSITIVITY_POLICY = TrustPolicy(allow_threshold=92.0, step_up_threshold=70.0, name="high_sensitivity")
