"""Thin re-export module: risk evaluation lives in rules.py; this module
is the stable public import path referenced by RFC-0001's component
table (`trust_engine/risk.py`)."""
from rules import evaluate_risk, DEFAULT_RULES, RiskRule  # noqa: F401
