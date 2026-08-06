"""
Verifier (client-side helper) — builds the CLIENT half of the handshake:
HELLO, ENTROPY, and the signed PROOF. Named `verifier` because from the
protocol's zero-knowledge-oriented framing (RFC-0001 §3) the client is
proving a claim that the server verifies; this module is the client's
counterpart to gateway/handshake.py's server orchestration.
"""
from __future__ import annotations

import sys
import uuid
import base64
from pathlib import Path
from typing import Any

_REF = Path(__file__).resolve().parents[1]
for p in [_REF, _REF / "identity-engine"]:
    sys.path.insert(0, str(p))

from crypto import SigningKeyPair, EphemeralKeyPair, csprng_bytes  # noqa: E402
from verification import compute_transcript_hash  # noqa: E402


class ClientSession:
    def __init__(self):
        self.signing_key = SigningKeyPair.generate()
        self.eph = EphemeralKeyPair.generate()

    def build_hello(self) -> dict:
        return {
            "idp": "1.0",
            "type": "HELLO",
            "msg_id": str(uuid.uuid4()),
            "body": {
                "client_version": "1.0.0",
                "supported_suites": ["ed25519-blake3-argon2id"],
                "nonce_c": base64.b64encode(csprng_bytes(32)).decode(),
                "client_eph_public": self.eph.public_key_b64,
            },
        }

    def build_entropy(self, device_dna_hash: str, behavior_raw: dict, context_raw: dict,
                       consent_receipt_id: str) -> dict:
        return {
            "idp": "1.0",
            "type": "ENTROPY",
            "msg_id": str(uuid.uuid4()),
            "body": {
                "device_dna_hash": device_dna_hash,
                "behavioral_sample": behavior_raw,
                "context": context_raw,
                "consent_receipt_id": consent_receipt_id,
            },
        }

    def build_proof(self, hello: dict, challenge: dict, entropy: dict, identity_ack: dict) -> dict:
        t_hash = compute_transcript_hash(hello, challenge, entropy, identity_ack)
        signature = self.signing_key.sign(t_hash)
        return {
            "idp": "1.0",
            "type": "PROOF",
            "msg_id": str(uuid.uuid4()),
            "body": {
                "signature": signature,
                "public_key": self.signing_key.public_key_b64,
            },
        }
