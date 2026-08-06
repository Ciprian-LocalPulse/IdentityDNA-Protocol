import sys
from pathlib import Path
_INT = Path(__file__).resolve().parents[1] / "integration"
sys.path.insert(0, str(_INT))
import conftest  # noqa: F401,E402
from demo_full_handshake import run_demo  # noqa: E402


def test_full_handshake_reaches_terminal_state():
    result = run_demo(verbose=False)
    assert result["final_state"] in ("ACTIVE", "DENIED", "REJECTED")


def test_full_handshake_produces_trust_result():
    result = run_demo(verbose=False)
    body = result["trust_result"]["body"]
    assert 0 <= body["trust_score"] <= 100
    assert body["decision"] in ("ALLOW", "STEP_UP", "DENY")


def test_trust_score_improves_across_repeated_sessions_same_device():
    """Regression test for the cold-start deadlock documented in
    CHANGELOG.md: a subject whose first session is DENIED (no baseline
    yet) must be able to climb to STEP_UP/ALLOW on subsequent sessions
    from the same recognized device, not remain permanently stuck."""
    from relationship import PersistentSubjectRegistry
    from history import PersistentTrustHistory
    from sqlite_store import SQLiteStore
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        results = []
        for _ in range(4):
            store = SQLiteStore(db_path)
            subjects = PersistentSubjectRegistry(store)
            history = PersistentTrustHistory(store)
            # monkey-patch run_demo's internal wiring by calling it with
            # explicit persist backends via db_path (run_demo opens its
            # own store internally, so just reuse the same db_path).
            result = run_demo(verbose=False, persist=True, db_path=db_path)
            results.append(result["trust_result"]["body"]["trust_score"])

    # First session should be denied (no baseline); a later session from
    # the same device must score strictly higher than the first.
    assert results[0] < results[1]
    assert results[-1] >= results[1]  # should not regress after improving
