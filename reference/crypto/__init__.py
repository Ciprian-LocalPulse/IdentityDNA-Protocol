"""
IdentityDNA Protocol — Cryptographic Core

Implements RFC-0001 §11 (Cryptographic Requirements). This module wraps
audited primitives only; it does NOT implement any cryptography from
scratch. Approved primitives per the RFC:

    Hashing        BLAKE3-256 (fallback: SHA3-256)
    Signatures     Ed25519
    Key Agreement  X25519
    KDF            HKDF-SHA256
    Password KDF   Argon2id
    AEAD           ChaCha20-Poly1305
    RNG            OS CSPRNG only
"""

from .primitives import (
    hash_blake3,
    hkdf,
    hkdf_expand_vector,
    argon2id_derive,
    aead_encrypt,
    aead_decrypt,
    csprng_bytes,
    canonical_json,
)
from .signatures import SigningKeyPair, verify_signature
from .keyagreement import EphemeralKeyPair, ecdh_shared_secret

__all__ = [
    "hash_blake3",
    "hkdf",
    "hkdf_expand_vector",
    "argon2id_derive",
    "aead_encrypt",
    "aead_decrypt",
    "csprng_bytes",
    "canonical_json",
    "SigningKeyPair",
    "verify_signature",
    "EphemeralKeyPair",
    "ecdh_shared_secret",
]
