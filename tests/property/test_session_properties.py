"""Property-based tests for reference/session-engine/."""
import conftest  # noqa: F401
from hypothesis import given, strategies as st, settings, HealthCheck

from crypto import EphemeralKeyPair, csprng_bytes
from generator import generate_initial_sdna
from rotator import rotate
from validator import SessionStore
from renewal import renew, RenewalError

_SLOW = settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


def _fresh_sdna(rotation_interval_s=300):
    server_eph = EphemeralKeyPair.generate()
    client_eph = EphemeralKeyPair.generate()
    transcript = csprng_bytes(32)
    return generate_initial_sdna(server_eph, client_eph.public_key_b64, transcript, rotation_interval_s)


@given(st.integers(min_value=1, max_value=10))
@_SLOW
def test_repeated_rotation_never_repeats_a_value(n_rotations):
    sdna = _fresh_sdna()
    seen = {sdna.sdna}
    for _ in range(n_rotations):
        sdna = rotate(sdna)
        assert sdna.sdna not in seen, "rotation produced a repeated Session DNA value"
        seen.add(sdna.sdna)


@given(st.integers(min_value=1, max_value=15))
@_SLOW
def test_generation_increments_by_exactly_one_per_rotation(n_rotations):
    sdna = _fresh_sdna()
    start_gen = sdna.generation
    for i in range(n_rotations):
        sdna = rotate(sdna)
        assert sdna.generation == start_gen + i + 1


@given(st.integers(min_value=1, max_value=10))
@_SLOW
def test_session_id_never_changes_across_rotations(n_rotations):
    sdna = _fresh_sdna()
    original_id = sdna.session_id
    for _ in range(n_rotations):
        sdna = rotate(sdna)
        assert sdna.session_id == original_id


@given(st.binary(min_size=32, max_size=32))
@_SLOW
def test_store_rejects_arbitrary_32byte_values_not_matching_current(random_32_bytes):
    store = SessionStore()
    sdna = _fresh_sdna()
    store.put(sdna)
    if random_32_bytes == sdna.sdna:
        return  # astronomically unlikely, but be correct about it
    ok, err = store.validate(sdna.session_id, random_32_bytes)
    assert not ok
    assert err == "ERR_SESSION_EXPIRED"  # RFC-0001 §5/§9: superseded/forged both map here


@given(st.integers(min_value=2, max_value=8))
@_SLOW
def test_only_latest_generation_ever_validates(n_rotations):
    """After N rotations, every OLDER generation must be rejected -- the
    'no session DNA reuse window' rule (RFC-0001 §9)."""
    store = SessionStore()
    sdna = _fresh_sdna()
    store.put(sdna)
    history = [sdna.sdna]
    for _ in range(n_rotations):
        sdna = renew(store, sdna.session_id, sdna.sdna)
        history.append(sdna.sdna)

    for old_value in history[:-1]:
        ok, err = store.validate(sdna.session_id, old_value)
        assert not ok, f"a superseded generation validated successfully: {old_value.hex()[:16]}"

    ok, _ = store.validate(sdna.session_id, history[-1])
    assert ok, "the current (latest) generation must still validate"


def test_revoked_session_rejects_even_the_current_generation():
    store = SessionStore()
    sdna = _fresh_sdna()
    store.put(sdna)
    store.revoke(sdna.session_id)
    ok, err = store.validate(sdna.session_id, sdna.sdna)
    assert not ok
    assert err == "ERR_SESSION_REVOKED"


@given(st.text(min_size=1, max_size=50))
def test_renew_unknown_session_always_raises(random_session_id):
    store = SessionStore()
    try:
        renew(store, random_session_id, csprng_bytes(32))
        assert False, "renew() should have raised for an unknown session_id"
    except RenewalError as e:
        assert e.code == "ERR_SESSION_EXPIRED"
