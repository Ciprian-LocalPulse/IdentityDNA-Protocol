import conftest  # noqa: F401
from crypto import EphemeralKeyPair
from generator import generate_initial_sdna
from rotator import rotate
from expiration import is_expired
from validator import SessionStore
from renewal import renew, RenewalError
import pytest


def _fresh_sdna():
    server_eph = EphemeralKeyPair.generate()
    client_eph = EphemeralKeyPair.generate()
    return generate_initial_sdna(server_eph, client_eph.public_key_b64, b"x" * 32)


def test_sdna_is_32_bytes():
    sdna = _fresh_sdna()
    assert len(sdna.sdna) == 32


def test_rotation_changes_value_and_generation():
    sdna0 = _fresh_sdna()
    sdna1 = rotate(sdna0)
    assert sdna1.sdna != sdna0.sdna
    assert sdna1.generation == sdna0.generation + 1
    assert sdna1.session_id == sdna0.session_id


def test_fresh_session_not_expired():
    sdna = _fresh_sdna()
    assert not is_expired(sdna)


def test_store_rejects_superseded_generation():
    store = SessionStore()
    sdna0 = _fresh_sdna()
    store.put(sdna0)
    ok, _ = store.validate(sdna0.session_id, sdna0.sdna)
    assert ok

    rotated = renew(store, sdna0.session_id, sdna0.sdna)
    ok, err = store.validate(sdna0.session_id, sdna0.sdna)
    assert not ok
    assert err == "ERR_SESSION_EXPIRED"

    ok, _ = store.validate(sdna0.session_id, rotated.sdna)
    assert ok


def test_revoked_session_rejected():
    store = SessionStore()
    sdna0 = _fresh_sdna()
    store.put(sdna0)
    store.revoke(sdna0.session_id)
    ok, err = store.validate(sdna0.session_id, sdna0.sdna)
    assert not ok
    assert err == "ERR_SESSION_REVOKED"


def test_renew_unknown_session_raises():
    store = SessionStore()
    with pytest.raises(RenewalError):
        renew(store, "does-not-exist", b"x" * 32)
