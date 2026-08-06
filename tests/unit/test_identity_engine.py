import conftest  # noqa: F401
import pytest
from identity_vector import compile_identity_vector, DegenerateInputError

DEVICE = {"platform": "Linux", "screen_class": "1920x1080", "timezone_offset_min": 120,
          "language": "ro", "color_depth_class": "24bit", "hardware_concurrency_class": "4-8",
          "gpu_vendor_class": "intel"}
BEHAVIOR = {"typing_cadence_ms": [120, 110, 130, 125], "pointer_entropy": 0.42}
CONTEXT = {"tz_offset_min": 120, "locale": "ro-RO"}


def test_identity_vector_is_unit_norm():
    iv = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a")
    norm_sq = sum(x * x for x in iv.vector)
    assert abs(norm_sq - 1.0) < 1e-9


def test_identity_vector_is_deterministic():
    iv1 = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a")
    iv2 = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a")
    assert iv1.vector == iv2.vector
    assert iv1.iv_digest == iv2.iv_digest


def test_identity_vector_changes_with_different_salt():
    iv1 = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a")
    iv2 = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-b")
    assert iv1.vector != iv2.vector


def test_self_distance_is_zero():
    iv = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a")
    assert abs(iv.distance(iv)) < 1e-9


def test_different_device_increases_distance():
    iv1 = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a")
    other_device = dict(DEVICE, platform="Windows", gpu_vendor_class="nvidia")
    iv2 = compile_identity_vector(other_device, BEHAVIOR, CONTEXT, "salt-a")
    assert iv1.distance(iv2) > 0.01


def test_weights_must_sum_to_one():
    with pytest.raises(AssertionError):
        compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, "salt-a",
                                 weights={"device": 0.9, "behavior": 0.9, "context": 0.2})


def test_malformed_typing_cadence_does_not_crash():
    """Regression test: normalize_behavior() must not raise when
    typing_cadence_ms is not a list (e.g. a malicious/buggy client sends
    a string). Found via property-based fuzzing -- see CHANGELOG.md."""
    malformed_behavior = {"typing_cadence_ms": "0", "pointer_entropy": 0.5}
    iv = compile_identity_vector(DEVICE, malformed_behavior, CONTEXT, "salt-a")
    assert len(iv.vector) == 256  # degrades gracefully instead of crashing


def test_malformed_context_tz_does_not_crash():
    malformed_context = {"tz_offset_min": "not-a-number", "locale": "ro-RO"}
    iv = compile_identity_vector(DEVICE, BEHAVIOR, malformed_context, "salt-a")
    assert len(iv.vector) == 256
