"""
Identity Engine — Identity Vector construction.

Implements formal-model.md §2 exactly. See RFC-0001 §7 for the normative
rule this module satisfies:

    IV = Normalize( f_device(D) (x) w_d + f_behavior(B) (x) w_b + f_context(C) (x) w_c )
"""
from __future__ import annotations

import math
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REFERENCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REFERENCE_ROOT))
sys.path.insert(0, str(_REFERENCE_ROOT / "entropy-engine"))
from normalizer import (  # noqa: E402
    normalize_device, normalize_behavior, normalize_context, digest_to_vector, VECTOR_DIM,
)

# formal-model.md §2.2 default weights
DEFAULT_WEIGHTS = {"device": 0.5, "behavior": 0.3, "context": 0.2}


class DegenerateInputError(ValueError):
    """Raised per RFC-0001 §7 when ||IV_raw||_2 == 0 (ERR_MALFORMED)."""


@dataclass
class IdentityVector:
    identity_vector_id: str
    vector: list[float]
    iv_digest: str  # hex, first 32 bytes of a hash over the vector — used in IDENTITY_ACK

    def cosine_similarity(self, other: "IdentityVector") -> float:
        # both vectors are unit-norm (formal-model.md §2.3), so cosine
        # similarity reduces to the dot product.
        return sum(a * b for a, b in zip(self.vector, other.vector))

    def distance(self, other: "IdentityVector") -> float:
        """formal-model.md §2.4"""
        return 1.0 - self.cosine_similarity(other)


def _weighted_sum(vd: list[float], vb: list[float], vc: list[float], weights: dict[str, float]) -> list[float]:
    return [
        vd[i] * weights["device"] + vb[i] * weights["behavior"] + vc[i] * weights["context"]
        for i in range(len(vd))
    ]


def _l2_normalize(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0.0:
        raise DegenerateInputError("Identity vector has zero norm (RFC-0001 §7): reject as ERR_MALFORMED")
    return [x / norm for x in v]


def compile_identity_vector(
    device_raw: dict[str, Any],
    behavior_raw: dict[str, Any],
    context_raw: dict[str, Any],
    rp_salt: str,
    weights: dict[str, float] | None = None,
    dim: int = VECTOR_DIM,
) -> IdentityVector:
    """The `identity_compiler` — formal-model.md §2, RFC-0001 §7."""
    weights = weights or DEFAULT_WEIGHTS
    assert abs(sum(weights.values()) - 1.0) < 1e-9, "weights must sum to 1 (formal-model.md §2.2)"

    device_digest = normalize_device(device_raw, rp_salt)
    behavior_digest = normalize_behavior(behavior_raw)
    context_digest = normalize_context(context_raw)

    vd = digest_to_vector(device_digest, dim)
    vb = digest_to_vector(behavior_digest, dim)
    vc = digest_to_vector(context_digest, dim)

    raw = _weighted_sum(vd, vb, vc, weights)
    normalized = _l2_normalize(raw)

    from crypto import hash_blake3
    iv_digest = hash_blake3(
        b"".join(int(x * 1e9).to_bytes(8, "big", signed=True) for x in normalized),
        domain="IDP-IV-DIGEST-v1",
    ).hex()

    return IdentityVector(
        identity_vector_id=str(uuid.uuid4()),
        vector=normalized,
        iv_digest=iv_digest,
    )
