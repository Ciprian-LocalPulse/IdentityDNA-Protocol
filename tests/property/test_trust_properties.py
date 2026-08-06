"""
Property-based tests for reference/trust-engine/. These specifically
target the class of bug found manually during Phase 1 testing (identity
score scaling, history deadlock) -- see CHANGELOG.md -- by fuzzing
across the full input space instead of relying on hand-picked examples.
"""
import conftest  # noqa: F401
from hypothesis import given, strategies as st, settings, HealthCheck, assume

from score import compute_identity_score, compute_context_score, compute_trust_score, clamp
from history import TrustHistory
from policies import TrustPolicy, Decision, DEFAULT_POLICY
from weights import TrustWeights

_SLOW = settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])

_distance = st.one_of(st.none(), st.floats(min_value=0.0, max_value=2.0, allow_nan=False))
_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# --- compute_identity_score: the exact formula that had a real bug ---

@given(_distance, _confidence)
@_SLOW
def test_identity_score_always_in_valid_range(distance, conf):
    s = compute_identity_score(distance, conf)
    assert -1e-9 <= s <= 100.0 * conf + 1e-9


@given(_confidence)
@_SLOW
def test_perfect_match_scores_strictly_more_than_no_baseline(conf):
    """Regression property for CHANGELOG.md's S_identity scaling bug:
    a perfect device match (d=0) must ALWAYS score higher than having
    no baseline at all (d=None), for any confidence > 0."""
    assume(conf > 0.001)
    s_perfect = compute_identity_score(0.0, conf)
    s_none = compute_identity_score(None, conf)
    assert s_perfect > s_none


@given(st.floats(min_value=0.0, max_value=2.0, allow_nan=False),
       st.floats(min_value=0.0, max_value=2.0, allow_nan=False),
       _confidence)
@_SLOW
def test_identity_score_monotonically_decreasing_in_distance(d1, d2, conf):
    """Smaller distance (more similar) must never score lower than a
    larger distance, for the same confidence."""
    assume(conf > 0.001)
    s1 = compute_identity_score(d1, conf)
    s2 = compute_identity_score(d2, conf)
    if d1 < d2:
        assert s1 >= s2 - 1e-9
    elif d1 > d2:
        assert s1 <= s2 + 1e-9


@given(st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=0, max_size=10))
@_SLOW
def test_context_score_always_in_range(priors):
    s = compute_context_score(priors)
    assert 0.0 <= s <= 100.0 + 1e-9


@given(st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=1, max_size=10))
@_SLOW
def test_context_score_never_exceeds_min_prior_scaled(priors):
    """Conjunctive (product) design: overall score can never exceed the
    single worst (lowest) prior scaled to 100 -- one bad signal caps
    the whole context score, by formal-model.md §3.5 design."""
    s = compute_context_score(priors)
    worst = min(priors) * 100.0
    assert s <= worst + 1e-6


# --- compute_trust_score: the end-to-end formula, always clamped ---

_risk_ctx = st.fixed_dictionaries({}, optional={
    "attempts_last_minute": st.integers(min_value=0, max_value=10000),
    "ip_reputation_score": st.integers(min_value=0, max_value=100),
    "is_tor_or_known_proxy": st.booleans(),
    "replay_detected": st.booleans(),
    "implied_velocity_kmh": st.floats(min_value=0, max_value=50000, allow_nan=False),
    "last_drift": st.floats(min_value=0, max_value=2, allow_nan=False),
    "behavioral_anomaly_flag": st.booleans(),
})


@given(_distance, st.integers(min_value=0, max_value=10),
       st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), max_size=5),
       _risk_ctx)
@_SLOW
def test_trust_score_always_clamped_0_100(distance, n_eff, priors, risk_ctx):
    hist = TrustHistory()
    result = compute_trust_score(
        identity_distance=distance, n_eff=n_eff, subject_id="fuzz-subject",
        history=hist, context_priors=priors, risk_context=risk_ctx,
    )
    assert 0.0 <= result.trust_score <= 100.0


@given(_distance, st.integers(min_value=0, max_value=10),
       st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), max_size=5),
       _risk_ctx)
@_SLOW
def test_trust_decision_consistent_with_policy_thresholds(distance, n_eff, priors, risk_ctx):
    hist = TrustHistory()
    result = compute_trust_score(
        identity_distance=distance, n_eff=n_eff, subject_id="fuzz-subject-2",
        history=hist, context_priors=priors, risk_context=risk_ctx,
    )
    if result.trust_score >= DEFAULT_POLICY.allow_threshold:
        assert result.decision == Decision.ALLOW
    elif result.trust_score >= DEFAULT_POLICY.step_up_threshold:
        assert result.decision == Decision.STEP_UP
    else:
        assert result.decision == Decision.DENY


@given(st.integers(min_value=0, max_value=20))
@_SLOW
def test_history_score_always_in_range_regardless_of_track_record(n_true):
    hist = TrustHistory()
    for i in range(n_true):
        hist.record("s", i % 2 == 0)  # mixed true/false
    score = hist.score("s")
    assert 0.0 <= score <= 100.0


@given(st.lists(st.booleans(), min_size=1, max_size=25))
@_SLOW
def test_history_all_true_gives_max_score(outcomes):
    hist = TrustHistory()
    for o in outcomes:
        hist.record("s", True)  # force all True regardless of `outcomes` sampling
    # Floating-point EWMA summation (formal-model.md §3.3) can accumulate
    # rounding error (e.g. 100.00000000000001) -- never compare floats
    # for exact equality; use a tight tolerance instead.
    assert abs(hist.score("s") - 100.0) < 1e-9


def test_policy_thresholds_are_ordered():
    """A malformed policy (step_up above allow) would make STEP_UP
    unreachable -- sanity check the default and high-sensitivity presets."""
    from policies import DEFAULT_POLICY, HIGH_SENSITIVITY_POLICY
    for policy in (DEFAULT_POLICY, HIGH_SENSITIVITY_POLICY):
        assert policy.step_up_threshold <= policy.allow_threshold
