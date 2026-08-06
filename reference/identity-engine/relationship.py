"""
Relationship — tracks the cross-session relationship between a claimed
principal (`subject_id`) and their enrolled baseline Identity Vector.

This is what lets formal-model.md §3.2 compute S_identity: `d(IV(t), IV_baseline)`
requires *some* durable notion of "the IV we've seen from this subject
before". This reference module stores that in memory; a production
deployment MUST use an access-controlled, encrypted-at-rest store, and
MUST apply the RFC-0001 §10 retention rules (never store raw signals,
only the derived IV / its digest).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity_vector import IdentityVector  # noqa: E402


class SubjectRegistry:
    """In-memory reference store: subject_id -> enrolled baseline IdentityVector."""

    def __init__(self) -> None:
        self._baselines: dict[str, IdentityVector] = {}

    def enroll(self, subject_id: str, iv: IdentityVector) -> None:
        self._baselines[subject_id] = iv

    def has_baseline(self, subject_id: str) -> bool:
        return subject_id in self._baselines

    def baseline_for(self, subject_id: str) -> IdentityVector | None:
        return self._baselines.get(subject_id)

    def relationship_distance(self, subject_id: str, current: IdentityVector) -> float | None:
        """Returns d(IV(t), IV_baseline), or None if no baseline exists
        yet (first-ever session for this subject — the caller MUST treat
        that as low-confidence, not as an automatic anomaly; see
        formal-model.md §5, confidence())."""
        baseline = self._baselines.get(subject_id)
        if baseline is None:
            return None
        return current.distance(baseline)

    def update_baseline_ewma(self, subject_id: str, current: IdentityVector, alpha: float = 0.1) -> None:
        """Optional slow drift adaptation: legitimate users' devices and
        behavior change gradually (new phone, healed typing injury, etc).
        An EWMA update on ACCEPTED sessions lets the baseline track slow,
        legitimate drift without ever fully trusting a single session's
        vector outright. Callers MUST only invoke this after a session
        reached decision=ALLOW."""
        baseline = self._baselines.get(subject_id)
        if baseline is None:
            self.enroll(subject_id, current)
            return
        import math
        blended = [
            (1 - alpha) * b + alpha * c
            for b, c in zip(baseline.vector, current.vector)
        ]
        norm = math.sqrt(sum(x * x for x in blended))
        blended = [x / norm for x in blended]
        from crypto import hash_blake3
        digest = hash_blake3(
            b"".join(int(x * 1e9).to_bytes(8, "big", signed=True) for x in blended),
            domain="IDP-IV-DIGEST-v1",
        ).hex()
        self._baselines[subject_id] = IdentityVector(
            identity_vector_id=baseline.identity_vector_id,
            vector=blended,
            iv_digest=digest,
        )


class PersistentSubjectRegistry(SubjectRegistry):
    """SQLite-backed variant of SubjectRegistry. Same interface, but
    `enroll` / `update_baseline_ewma` write through to disk and
    `baseline_for` reads through on cache miss, so baselines survive
    across process restarts (unlike the pure in-memory base class).

    See reference/storage/sqlite_store.py — only the derived Identity
    Vector floats + digest are persisted, never raw device/behavior/
    context signals (RFC-0001 §10).
    """

    def __init__(self, store) -> None:
        super().__init__()
        self._store = store

    def enroll(self, subject_id: str, iv: IdentityVector) -> None:
        super().enroll(subject_id, iv)
        self._store.put_baseline(subject_id, iv.identity_vector_id, iv.vector, iv.iv_digest)

    def has_baseline(self, subject_id: str) -> bool:
        if subject_id in self._baselines:
            return True
        return self._store.get_baseline(subject_id) is not None

    def baseline_for(self, subject_id: str) -> IdentityVector | None:
        if subject_id in self._baselines:
            return self._baselines[subject_id]
        row = self._store.get_baseline(subject_id)
        if row is None:
            return None
        iv = IdentityVector(
            identity_vector_id=row["identity_vector_id"],
            vector=row["vector"],
            iv_digest=row["iv_digest"],
        )
        self._baselines[subject_id] = iv  # warm the in-memory cache
        return iv

    def relationship_distance(self, subject_id: str, current: IdentityVector) -> float | None:
        baseline = self.baseline_for(subject_id)
        if baseline is None:
            return None
        return current.distance(baseline)

    def update_baseline_ewma(self, subject_id: str, current: IdentityVector, alpha: float = 0.1) -> None:
        baseline = self.baseline_for(subject_id)
        if baseline is None:
            self.enroll(subject_id, current)
            return
        import math
        blended = [(1 - alpha) * b + alpha * c for b, c in zip(baseline.vector, current.vector)]
        norm = math.sqrt(sum(x * x for x in blended))
        blended = [x / norm for x in blended]
        from crypto import hash_blake3
        digest = hash_blake3(
            b"".join(int(x * 1e9).to_bytes(8, "big", signed=True) for x in blended),
            domain="IDP-IV-DIGEST-v1",
        ).hex()
        updated = IdentityVector(identity_vector_id=baseline.identity_vector_id, vector=blended, iv_digest=digest)
        self._baselines[subject_id] = updated
        self._store.put_baseline(subject_id, updated.identity_vector_id, updated.vector, updated.iv_digest)
