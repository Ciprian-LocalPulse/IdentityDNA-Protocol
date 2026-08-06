"""
Risk rules — formal-model.md §3.4: R_risk(t) = sum_i severity_i * indicator_i(t).

Each rule is a small pure function: (session_context) -> (triggered: bool, severity: float).
Registering a new rule is additive and MUST be documented in
docs/architecture/threat-model.md when it corresponds to a named threat.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class RiskRule:
    name: str
    severity: float
    check: Callable[[dict[str, Any]], bool]
    threat_ref: str  # cross-reference into threat-model.md §3


def rule_impossible_travel(ctx: dict[str, Any]) -> bool:
    """Two geolocations implying a velocity beyond plausible travel
    (default threshold 900 km/h, i.e. faster than commercial flight)."""
    v = ctx.get("implied_velocity_kmh")
    return v is not None and v > 900


def rule_known_bad_device(ctx: dict[str, Any]) -> bool:
    return bool(ctx.get("device_dna_hash") in ctx.get("blocklisted_device_hashes", set()))


def rule_ip_reputation(ctx: dict[str, Any]) -> bool:
    return ctx.get("ip_reputation_score", 100) < 30


def rule_tor_or_proxy(ctx: dict[str, Any]) -> bool:
    return bool(ctx.get("is_tor_or_known_proxy", False))


def rule_replay_attempt(ctx: dict[str, Any]) -> bool:
    return bool(ctx.get("replay_detected", False))


def rule_velocity_abuse(ctx: dict[str, Any]) -> bool:
    """Excessive authentication attempts from the same origin (threat-model §3.3)."""
    return ctx.get("attempts_last_minute", 0) > 10


def rule_device_dna_drift(ctx: dict[str, Any]) -> bool:
    """Identity distance between consecutive samples exceeds threshold
    (formal-model.md §2.4; threat-model.md §3.6 Device Theft signal)."""
    drift = ctx.get("last_drift")
    return drift is not None and drift > 0.6


def rule_behavioral_anomaly(ctx: dict[str, Any]) -> bool:
    return bool(ctx.get("behavioral_anomaly_flag", False))


DEFAULT_RULES: list[RiskRule] = [
    RiskRule("impossible_travel", 40.0, rule_impossible_travel, "threat-model.md §3.6"),
    RiskRule("known_bad_device", 40.0, rule_known_bad_device, "threat-model.md §3.4"),
    RiskRule("ip_reputation", 20.0, rule_ip_reputation, "threat-model.md §3.5"),
    RiskRule("tor_or_proxy", 15.0, rule_tor_or_proxy, "threat-model.md §3.2"),
    RiskRule("replay_attempt", 40.0, rule_replay_attempt, "threat-model.md §3.1"),
    RiskRule("velocity_abuse", 25.0, rule_velocity_abuse, "threat-model.md §3.3"),
    RiskRule("device_dna_drift", 20.0, rule_device_dna_drift, "threat-model.md §3.6"),
    RiskRule("behavioral_anomaly", 10.0, rule_behavioral_anomaly, "threat-model.md §3.6"),
]


def evaluate_risk(ctx: dict[str, Any], rules: list[RiskRule] | None = None) -> tuple[float, list[str]]:
    rules = rules or DEFAULT_RULES
    total = 0.0
    triggered = []
    for r in rules:
        if r.check(ctx):
            total += r.severity
            triggered.append(r.name)
    return total, triggered
