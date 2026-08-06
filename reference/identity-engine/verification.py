"""
Verification — validates the PROOF message against the handshake
transcript (RFC-0001 §4.5, §11.2). This is the Verifier's core routine:
it never learns any secret, it only checks a signature over a hash.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REFERENCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REFERENCE_ROOT))
from crypto import hash_blake3, canonical_json, verify_signature  # noqa: E402


def compute_transcript_hash(hello: dict, challenge: dict, entropy: dict, identity_ack: dict) -> bytes:
    """RFC-0001 §11.2:
    transcript_hash = BLAKE3("IDP-TRANSCRIPT-v1" || HELLO || CHALLENGE || ENTROPY || IDENTITY_ACK)
    """
    return hash_blake3(
        canonical_json(hello),
        canonical_json(challenge),
        canonical_json(entropy),
        canonical_json(identity_ack),
        domain="IDP-TRANSCRIPT-v1",
    )


def verify_proof(hello: dict, challenge: dict, entropy: dict, identity_ack: dict,
                  public_key_b64: str, signature_b64: str) -> tuple[bool, bytes]:
    """Returns (is_valid, transcript_hash). RFC-0001 §6: on failure the
    caller MUST emit ERR_SIGNATURE_INVALID and MUST NOT proceed to trust
    evaluation for this handshake attempt."""
    t_hash = compute_transcript_hash(hello, challenge, entropy, identity_ack)
    ok = verify_signature(public_key_b64, t_hash, signature_b64)
    return ok, t_hash
