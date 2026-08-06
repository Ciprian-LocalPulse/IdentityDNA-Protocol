"""
Entropy Engine — normalization layer.

Implements formal-model.md §2.1 (f_device, f_behavior, f_context) and the
RFC-0001 §10 Privacy Addendum. This module is the ONLY place in the
reference implementation allowed to touch raw device/behavioral signals;
everything downstream sees only hashed/normalized output.

Design rule (RFC-0001 §10.3): raw high-entropy identifiers never leave
this module. Callers get a hash and a float vector, never the raw dict.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto import hash_blake3, hkdf_expand_vector  # noqa: E402

VECTOR_DIM = 256

# Fields explicitly allowed for Device DNA collection. Anything not in this
# allow-list MUST be dropped by normalize_device (RFC-0001 §10.1/10.3):
# collection must be disclosed, and we enforce that disclosure at the
# allow-list boundary rather than trusting callers to behave.
_ALLOWED_DEVICE_FIELDS = {
    "platform",            # coarse OS family, e.g. "Linux", "Windows", "macOS"
    "screen_class",        # bucketed resolution class, NOT exact pixels
    "timezone_offset_min",
    "language",
    "color_depth_class",   # bucketed, e.g. "24bit"
    "hardware_concurrency_class",  # bucketed CPU core count, e.g. "4-8"
    "gpu_vendor_class",    # vendor only (e.g. "intel", "nvidia", "apple"), not full string
}


def normalize_device(raw: dict[str, Any], rp_salt: str) -> bytes:
    """Normalize + hash device signals. `rp_salt` is a per-Relying-Party
    salt (RFC-0001 §10.4 / threat-model §3.7) preventing cross-RP linkage
    of the same physical device by a compromised operator.

    Only allow-listed, already-bucketed fields participate. Unknown or
    disallowed keys are silently dropped (fail closed, not fail open).
    """
    filtered = {k: str(raw.get(k, "unknown")) for k in sorted(_ALLOWED_DEVICE_FIELDS)}
    canonical = "|".join(f"{k}={v}" for k, v in filtered.items())
    return hash_blake3(canonical.encode("utf-8"), rp_salt.encode("utf-8"),
                        domain="IDP-DEVICE-DNA-v1")


def normalize_behavior(raw: dict[str, Any]) -> bytes:
    """Normalize behavioral samples (typing cadence, pointer entropy) into
    a fixed digest. Raw timing arrays are reduced to summary statistics —
    mean, stddev, and a coarse histogram — never transmitted/stored as
    raw per-keystroke timing (which can itself be a biometric identifier
    with its own privacy weight)."""
    cadence = raw.get("typing_cadence_ms", [])
    pointer_entropy = float(raw.get("pointer_entropy", 0.0))

    if cadence:
        mean = sum(cadence) / len(cadence)
        variance = sum((x - mean) ** 2 for x in cadence) / len(cadence)
        stddev = variance ** 0.5
    else:
        mean, stddev = 0.0, 0.0

    summary = f"mean={mean:.2f}|std={stddev:.2f}|ptr={pointer_entropy:.4f}"
    return hash_blake3(summary.encode("utf-8"), domain="IDP-BEHAVIOR-v1")


def normalize_context(raw: dict[str, Any]) -> bytes:
    """Normalize contextual signals (timezone, locale). Coarse by design —
    context is a corroborating signal, not a fingerprinting vector."""
    tz = int(raw.get("tz_offset_min", 0))
    locale = str(raw.get("locale", "unknown"))
    summary = f"tz={tz}|locale={locale}"
    return hash_blake3(summary.encode("utf-8"), domain="IDP-CONTEXT-v1")


def digest_to_vector(digest: bytes, n: int = VECTOR_DIM) -> list[float]:
    """formal-model.md §2.1 Expand(seed, n)."""
    return hkdf_expand_vector(digest, n)
