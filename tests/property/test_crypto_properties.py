"""
Property-based tests for reference/crypto/. These fuzz across thousands
of random inputs (Hypothesis default: 100 examples/test, shrinking on
failure) to check invariants that RFC-0001 §11 requires but that a
handful of hand-picked unit test values can't exhaustively cover.
"""
import conftest  # noqa: F401
from hypothesis import given, strategies as st, settings, HealthCheck

from crypto import hash_blake3, hkdf, SigningKeyPair, verify_signature, EphemeralKeyPair, ecdh_shared_secret, csprng_bytes

_SLOW = settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])


# --- hashing (RFC-0001 §11.3 domain separation) ---

@given(st.binary(min_size=0, max_size=256), st.binary(min_size=0, max_size=256))
@_SLOW
def test_hash_deterministic_for_any_input(a, b):
    h1 = hash_blake3(a, b, domain="FUZZ-DOMAIN")
    h2 = hash_blake3(a, b, domain="FUZZ-DOMAIN")
    assert h1 == h2
    assert len(h1) == 32


@given(st.binary(min_size=0, max_size=64))
@_SLOW
def test_hash_domain_separation_never_collides_for_sampled_domains(payload):
    domains = ["IDP-DEVICE-DNA-v1", "IDP-BEHAVIOR-v1", "IDP-CONTEXT-v1",
               "IDP-TRANSCRIPT-v1", "IDP-SESSION-DNA-v1", "IDP-ROTATE-v1"]
    outputs = {hash_blake3(payload, domain=d) for d in domains}
    # same payload, 6 different domains -> 6 distinct digests (no collision observed)
    assert len(outputs) == len(domains)


@given(st.binary(min_size=1, max_size=64))
def test_hash_requires_nonempty_domain(payload):
    import pytest
    with pytest.raises(ValueError):
        hash_blake3(payload, domain="")


# --- HKDF ---

@given(st.binary(min_size=1, max_size=128), st.integers(min_value=1, max_value=255))
@_SLOW
def test_hkdf_output_length_always_matches_request(ikm, length):
    out = hkdf(ikm, salt=b"fuzz-salt", info="fuzz-info", length=length)
    assert len(out) == length


@given(st.binary(min_size=1, max_size=64), st.binary(min_size=1, max_size=64))
def test_hkdf_different_salt_gives_different_output(ikm, salt2):
    if salt2 == b"salt1":
        return
    out1 = hkdf(ikm, salt=b"salt1", info="i", length=32)
    out2 = hkdf(ikm, salt=salt2, info="i", length=32)
    assert out1 != out2


# --- Ed25519 signatures ---

@given(st.binary(min_size=0, max_size=512))
@_SLOW
def test_signature_always_verifies_for_correct_key(message):
    kp = SigningKeyPair.generate()
    sig = kp.sign(message)
    assert verify_signature(kp.public_key_b64, message, sig)


@given(st.binary(min_size=1, max_size=256), st.binary(min_size=1, max_size=256))
@_SLOW
def test_signature_never_verifies_for_wrong_message(message, tampered):
    if message == tampered:
        return
    kp = SigningKeyPair.generate()
    sig = kp.sign(message)
    assert not verify_signature(kp.public_key_b64, tampered, sig)


@given(st.binary(min_size=0, max_size=128))
def test_signature_never_verifies_for_wrong_key(message):
    kp_a = SigningKeyPair.generate()
    kp_b = SigningKeyPair.generate()
    sig = kp_a.sign(message)
    assert not verify_signature(kp_b.public_key_b64, message, sig)


def test_signature_rejects_malformed_public_key():
    kp = SigningKeyPair.generate()
    sig = kp.sign(b"msg")
    assert not verify_signature("not-valid-base64!!!", b"msg", sig)
    assert not verify_signature("", b"msg", sig)


def test_signature_rejects_malformed_signature():
    kp = SigningKeyPair.generate()
    assert not verify_signature(kp.public_key_b64, b"msg", "not-a-valid-signature")


# --- X25519 ECDH ---

def test_ecdh_symmetric_across_many_random_keypairs():
    for _ in range(50):
        a = EphemeralKeyPair.generate()
        b = EphemeralKeyPair.generate()
        assert ecdh_shared_secret(a, b.public_key_b64) == ecdh_shared_secret(b, a.public_key_b64)


def test_ecdh_distinct_keypairs_give_distinct_secrets():
    a = EphemeralKeyPair.generate()
    b = EphemeralKeyPair.generate()
    c = EphemeralKeyPair.generate()
    secret_ab = ecdh_shared_secret(a, b.public_key_b64)
    secret_ac = ecdh_shared_secret(a, c.public_key_b64)
    assert secret_ab != secret_ac


# --- CSPRNG ---

@given(st.integers(min_value=1, max_value=1024))
def test_csprng_length_matches_request(n):
    assert len(csprng_bytes(n)) == n


def test_csprng_no_collisions_in_1000_draws():
    draws = {csprng_bytes(32) for _ in range(1000)}
    assert len(draws) == 1000  # astronomically unlikely to collide at 256 bits
