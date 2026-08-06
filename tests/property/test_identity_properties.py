"""Property-based tests for reference/identity-engine/identity_vector.py."""
import conftest  # noqa: F401
import math
from hypothesis import given, strategies as st, settings, HealthCheck

from identity_vector import compile_identity_vector, DegenerateInputError

_SLOW = settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])

# Fuzzed device/behavior/context dicts -- deliberately includes empty
# strings, extreme numbers, unicode, and fields NOT in the allow-list
# (which normalizer.py must silently drop, RFC-0001 §10.3 fail-closed).
_json_scalar = st.one_of(st.text(max_size=50), st.integers(min_value=-10**6, max_value=10**6), st.floats(allow_nan=False, allow_infinity=False))
_fuzz_dict = st.dictionaries(st.text(min_size=0, max_size=20), _json_scalar, max_size=10)
_rp_salt = st.text(min_size=0, max_size=100)


@given(_fuzz_dict, _fuzz_dict, _fuzz_dict, _rp_salt)
@_SLOW
def test_identity_vector_always_unit_norm_or_raises(device, behavior, context, salt):
    try:
        iv = compile_identity_vector(device, behavior, context, salt)
    except DegenerateInputError:
        return  # acceptable: RFC-0001 §7 mandates rejecting zero-norm input
    norm_sq = sum(x * x for x in iv.vector)
    assert abs(norm_sq - 1.0) < 1e-6, f"norm^2={norm_sq} not ~1.0"
    assert len(iv.vector) == 256
    assert len(iv.iv_digest) == 64  # hex-encoded 32 bytes


@given(_fuzz_dict, _fuzz_dict, _fuzz_dict, _rp_salt)
@_SLOW
def test_identity_vector_deterministic_for_same_input(device, behavior, context, salt):
    try:
        iv1 = compile_identity_vector(device, behavior, context, salt)
        iv2 = compile_identity_vector(device, behavior, context, salt)
    except DegenerateInputError:
        return
    assert iv1.vector == iv2.vector
    assert iv1.iv_digest == iv2.iv_digest
    # identity_vector_id is a fresh uuid4 each call -- must NOT be equal
    assert iv1.identity_vector_id != iv2.identity_vector_id


@given(_fuzz_dict, _fuzz_dict, _fuzz_dict, _rp_salt)
@_SLOW
def test_self_distance_always_near_zero(device, behavior, context, salt):
    try:
        iv = compile_identity_vector(device, behavior, context, salt)
    except DegenerateInputError:
        return
    d = iv.distance(iv)
    assert abs(d) < 1e-6


@given(_fuzz_dict, _fuzz_dict, _fuzz_dict, _rp_salt, _rp_salt)
@_SLOW
def test_distance_always_in_valid_range(device, behavior, context, salt_a, salt_b):
    try:
        iv1 = compile_identity_vector(device, behavior, context, salt_a)
        iv2 = compile_identity_vector(device, behavior, context, salt_b)
    except DegenerateInputError:
        return
    d = iv1.distance(iv2)
    assert -1e-9 <= d <= 2.0 + 1e-9, f"distance {d} out of [0,2] range"


@given(_fuzz_dict, _fuzz_dict, _fuzz_dict, _rp_salt)
@_SLOW
def test_unknown_fields_do_not_crash_and_are_dropped(device, behavior, context, salt):
    """RFC-0001 §10.3: fields not in the Device DNA allow-list must be
    silently dropped, not cause an error or leak into the digest
    differently than an allow-listed-only version would (fail-closed)."""
    try:
        iv_with_extra = compile_identity_vector(device, behavior, context, salt)
        # Adding a bunch of clearly-not-allow-listed junk keys should not change the result
        junk = dict(device)
        junk["totally_not_allowlisted_field_xyz"] = "some-invasive-fingerprint-value"
        junk["another_random_key"] = 12345
        iv_with_junk = compile_identity_vector(junk, behavior, context, salt)
    except DegenerateInputError:
        return
    assert iv_with_extra.vector == iv_with_junk.vector, "non-allow-listed fields leaked into the Identity Vector"
