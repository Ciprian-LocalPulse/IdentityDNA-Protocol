import conftest  # noqa: F401
from crypto import hash_blake3, hkdf, SigningKeyPair, verify_signature, EphemeralKeyPair, ecdh_shared_secret, csprng_bytes


def test_hash_domain_separation_changes_output():
    h1 = hash_blake3(b"same-input", domain="DOMAIN-A")
    h2 = hash_blake3(b"same-input", domain="DOMAIN-B")
    assert h1 != h2


def test_hash_deterministic():
    assert hash_blake3(b"x", domain="D") == hash_blake3(b"x", domain="D")


def test_hkdf_length():
    out = hkdf(b"ikm-material", salt=b"salt", info="test", length=48)
    assert len(out) == 48


def test_signature_roundtrip():
    kp = SigningKeyPair.generate()
    msg = b"transcript-hash-placeholder-32b"
    sig = kp.sign(msg)
    assert verify_signature(kp.public_key_b64, msg, sig)


def test_signature_rejects_tampered_message():
    kp = SigningKeyPair.generate()
    sig = kp.sign(b"original-message-32-bytes-long!")
    assert not verify_signature(kp.public_key_b64, b"tampered-message-32-bytes-long!", sig)


def test_ecdh_symmetric():
    a = EphemeralKeyPair.generate()
    b = EphemeralKeyPair.generate()
    shared_ab = ecdh_shared_secret(a, b.public_key_b64)
    shared_ba = ecdh_shared_secret(b, a.public_key_b64)
    assert shared_ab == shared_ba


def test_csprng_length_and_uniqueness():
    a = csprng_bytes(32)
    b = csprng_bytes(32)
    assert len(a) == 32 and len(b) == 32
    assert a != b
