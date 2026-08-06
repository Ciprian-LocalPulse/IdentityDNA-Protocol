"""
Primitive wrappers. Every function here is a thin, auditable wrapper around
a well-established library. See RFC-0001 §11.1 for the approved-primitives
table and §11.3 for the domain-separation requirement.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

try:
    import blake3 as _blake3_lib
    _HAS_BLAKE3 = True
except ImportError:  # pragma: no cover - fallback path
    _HAS_BLAKE3 = False

from argon2.low_level import hash_secret_raw, Type as _Argon2Type
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand
from cryptography.hazmat.primitives import hashes as _crypto_hashes


def csprng_bytes(n: int) -> bytes:
    """RFC-0001 §11.1: RNG MUST be a CSPRNG. os.urandom is backed by the
    platform CSPRNG (getrandom(2) / CryptGenRandom / arc4random)."""
    if n <= 0:
        raise ValueError("n must be positive")
    return os.urandom(n)


def hash_blake3(*parts: bytes, domain: str) -> bytes:
    """Domain-separated BLAKE3-256 (or SHA3-256 fallback) per RFC-0001 §11.3.

    Every call site MUST supply a unique `domain` string tag. This function
    concatenates the domain tag (length-prefixed) ahead of the parts so
    that two different domains can never produce colliding inputs to the
    hash function via concatenation ambiguity.
    """
    if not domain:
        raise ValueError("domain separation tag is required (RFC-0001 §11.3)")
    domain_bytes = domain.encode("ascii")
    prefix = len(domain_bytes).to_bytes(2, "big") + domain_bytes
    payload = prefix + b"".join(len(p).to_bytes(4, "big") + p for p in parts)

    if _HAS_BLAKE3:
        return _blake3_lib.blake3(payload).digest(32)
    return hashlib.sha3_256(payload).digest()


def hkdf(ikm: bytes, salt: Optional[bytes], info: str, length: int = 32) -> bytes:
    """HKDF-SHA256 (RFC 5869). Used for Session DNA derivation (RFC-0001 §9)."""
    hk = HKDF(
        algorithm=_crypto_hashes.SHA256(),
        length=length,
        salt=salt,
        info=info.encode("ascii"),
    )
    return hk.derive(ikm)


def hkdf_expand_vector(seed: bytes, n: int) -> list[float]:
    """Expand a 32-byte seed into `n` floats in [0,1] via HKDF-Expand.

    Used by the Identity Engine layer functions (formal-model.md §2.1).
    """
    expander = HKDFExpand(algorithm=_crypto_hashes.SHA256(), length=n, info=b"IDP-VECTOR-EXPAND-v1")
    raw = expander.derive(seed)
    return [b / 255.0 for b in raw]


def argon2id_derive(secret: bytes, salt: bytes, length: int = 32,
                     time_cost: int = 3, memory_cost_kib: int = 65536,
                     parallelism: int = 2) -> bytes:
    """Argon2id, for the narrow case of deriving key material from a
    human-supplied low-entropy secret (RFC-0001 §11.1). NOT used for
    Session DNA or Identity Vector derivation — those use HKDF over
    high-entropy ECDH/random material, which is the correct primitive
    (Argon2id would be needlessly expensive and add no security there)."""
    if len(salt) < 8:
        raise ValueError("Argon2 salt must be >= 8 bytes")
    return hash_secret_raw(
        secret=secret,
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost_kib,
        parallelism=parallelism,
        hash_len=length,
        type=_Argon2Type.ID,
    )


def aead_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = b"") -> tuple[bytes, bytes]:
    """ChaCha20-Poly1305 AEAD. Returns (nonce, ciphertext_with_tag)."""
    if len(key) != 32:
        raise ValueError("ChaCha20-Poly1305 key must be 32 bytes")
    nonce = csprng_bytes(12)
    aead = ChaCha20Poly1305(key)
    ct = aead.encrypt(nonce, plaintext, associated_data)
    return nonce, ct


def aead_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
    aead = ChaCha20Poly1305(key)
    return aead.decrypt(nonce, ciphertext, associated_data)


def canonical_json(obj) -> bytes:
    """RFC 8785-style canonicalization (sorted keys, compact separators,
    no insignificant whitespace) — sufficient for our purposes since we
    control both encoder and decoder. Used to build the transcript hash
    input (RFC-0001 §11.2)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
