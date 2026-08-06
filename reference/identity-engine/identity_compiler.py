"""
Identity Compiler — public entry point of the Identity Engine.

Wraps identity_vector.compile_identity_vector with the RFC-0001 §4.3 /
§10.2 consent-gating rule: entropy MUST NOT be compiled into an Identity
Vector without a valid, unexpired consent receipt.
"""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from identity_vector import compile_identity_vector, IdentityVector, DegenerateInputError  # noqa: E402


class ConsentMissingError(PermissionError):
    """Maps to RFC-0001 ERR_CONSENT_MISSING."""


@dataclass
class ConsentReceipt:
    consent_receipt_id: str
    subject_id: str
    scopes: list[str]
    issued_at: datetime
    expires_at: datetime

    def is_valid(self, required_scope: str = "device_dna") -> bool:
        now = datetime.now(timezone.utc)
        return (
            required_scope in self.scopes
            and self.issued_at <= now <= self.expires_at
        )


class IdentityCompiler:
    """Stateless compiler; a fresh instance per RP is fine (only carries
    the rp_salt / weight configuration, no secret material)."""

    def __init__(self, rp_salt: str, weights: dict[str, float] | None = None):
        self.rp_salt = rp_salt
        self.weights = weights

    def compile(
        self,
        device_raw: dict[str, Any],
        behavior_raw: dict[str, Any],
        context_raw: dict[str, Any],
        consent: ConsentReceipt,
    ) -> IdentityVector:
        if not consent.is_valid():
            raise ConsentMissingError(
                f"consent receipt {consent.consent_receipt_id} invalid or expired (RFC-0001 ERR_CONSENT_MISSING)"
            )
        return compile_identity_vector(device_raw, behavior_raw, context_raw, self.rp_salt, self.weights)
