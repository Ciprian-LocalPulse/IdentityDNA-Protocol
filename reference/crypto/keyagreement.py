"""X25519 ephemeral key agreement per RFC-0001 §11.1 / RFC 7748.

Used exclusively to derive SDNA_0 (RFC-0001 §9) with forward secrecy:
both parties generate a fresh ephemeral keypair per session and discard
the private scalar once the shared secret is derived.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from nacl.public import PrivateKey, PublicKey, Box


@dataclass
class EphemeralKeyPair:
    private_key: PrivateKey

    @classmethod
    def generate(cls) -> "EphemeralKeyPair":
        return cls(private_key=PrivateKey.generate())

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(bytes(self.private_key.public_key)).decode("ascii")


def ecdh_shared_secret(own: EphemeralKeyPair, peer_public_key_b64: str) -> bytes:
    """Raw X25519 shared secret (32 bytes). MUST be run through HKDF
    (see primitives.hkdf) before use as key material — never used raw."""
    peer_pub = PublicKey(base64.b64decode(peer_public_key_b64))
    box = Box(own.private_key, peer_pub)
    # PyNaCl's Box derives via HSalsa20 internally; for raw X25519 ECDH we
    # use the lower-level scalarmult primitive to match RFC-0001 exactly
    # (HKDF applied by the caller, not baked into a Box use).
    from nacl.bindings import crypto_scalarmult
    return crypto_scalarmult(bytes(own.private_key), bytes(peer_pub))
