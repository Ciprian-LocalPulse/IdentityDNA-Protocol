"""Ed25519 signing per RFC-0001 §11.1 / RFC 8032."""
from __future__ import annotations

import base64
from dataclasses import dataclass

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


@dataclass
class SigningKeyPair:
    signing_key: SigningKey

    @classmethod
    def generate(cls) -> "SigningKeyPair":
        return cls(signing_key=SigningKey.generate())

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(bytes(self.signing_key.verify_key)).decode("ascii")

    def sign(self, transcript_hash: bytes) -> str:
        """Signs a transcript hash (RFC-0001 §11.2), not raw fields, so
        the proof is bound to the entire handshake so far."""
        sig = self.signing_key.sign(transcript_hash).signature
        return base64.b64encode(sig).decode("ascii")


def verify_signature(public_key_b64: str, transcript_hash: bytes, signature_b64: str) -> bool:
    try:
        vk = VerifyKey(base64.b64decode(public_key_b64))
        vk.verify(transcript_hash, base64.b64decode(signature_b64))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False
