import conftest  # noqa: F401
from score import compute_identity_score, compute_context_score, compute_trust_score, clamp
from history import TrustHistory
from policies import Decision, DEFAULT_POLICY


def test_worked_example_matches_formal_model_doc():
    """Cross-check against docs/mathematics/formal-model.md §7."""
    s_identity = compute_identity_score(distance=0.04, conf=0.93)
    assert round(s_identity, 2) == 91.14
    ts = clamp(0.35 * s_identity + 0.30 * 88 + 0.15 * 95 - 0.20 * 6, 0, 100)
    assert round(ts, 2) == 71.35
    assert DEFAULT_POLICY.decide(ts) == Decision.STEP_UP


def test_no_baseline_treated_as_neutral_midpoint():
    """formal-model.md §3.2.1: distance=None must equal distance=1.0
    (orthogonal/neutral), NOT distance=0 (perfect match). This is the
    scaling bug documented in CHANGELOG.md — a perfect match must score
    strictly higher than 'no information yet'."""
    s_no_baseline = compute_identity_score(distance=None, conf=0.93)
    s_neutral_d1 = compute_identity_score(distance=1.0, conf=0.93)
    s_perfect_match = compute_identity_score(distance=0.0, conf=0.93)
    assert s_no_baseline == s_neutral_d1
    assert s_perfect_match > s_no_baseline
    assert round(s_perfect_match, 2) == round(2 * s_no_baseline, 2)  # 100*conf vs 50*conf


def test_context_score_is_conjunctive():
    conjunctive = compute_context_score([0.99, 0.99, 0.05])
    assert conjunctive < 10.0


def test_trust_score_clamped_to_range():
    hist = TrustHistory()
    result = compute_trust_score(
        identity_distance=2.0, n_eff=0, subject_id="s", history=hist,
        context_priors=[0.0], risk_context={"attempts_last_minute": 999, "ip_reputation_score": 0},
    )
    assert 0.0 <= result.trust_score <= 100.0
    assert result.decision == Decision.DENY


def test_history_improves_with_good_track_record():
    hist = TrustHistory()
    for _ in range(10):
        hist.record("alice", True)
    assert hist.score("alice") > 90.0


def test_history_neutral_for_unknown_subject():
    hist = TrustHistory()
    assert hist.score("never-seen") == 50.0
