"""History Score — formal-model.md §3.3, exponentially-weighted recency."""
from __future__ import annotations
from collections import deque

LAMBDA_DEFAULT = 0.85
K_DEFAULT = 20


class TrustHistory:
    """Per-subject rolling history of session outcomes (True = accepted
    without step-up). Reference impl keeps this in memory; production
    deployments MUST persist it (see relationship.py's storage note)."""

    def __init__(self, k: int = K_DEFAULT):
        self.k = k
        self._by_subject: dict[str, deque[bool]] = {}

    def record(self, subject_id: str, accepted_without_stepup: bool) -> None:
        """Despite the parameter name (kept for backward compatibility
        with existing call sites), formal-model.md §3.3.1 defines
        match(t-k)=1 for decision in {ALLOW, STEP_UP}, not ALLOW only —
        see the rationale there. Callers pass True for any non-DENY
        outcome."""
        dq = self._by_subject.setdefault(subject_id, deque(maxlen=self.k))
        dq.append(accepted_without_stepup)

    def score(self, subject_id: str, lam: float = LAMBDA_DEFAULT) -> float:
        """S_history(t) = 100 * sum(lam^(k-1) * match) / sum(lam^(k-1))"""
        dq = self._by_subject.get(subject_id)
        if not dq:
            return 50.0  # neutral prior for a first-ever session (formal-model.md §5 confidence handles the rest)
        # most recent last in deque -> weight most recent highest
        n = len(dq)
        num = 0.0
        den = 0.0
        for i, match in enumerate(reversed(dq)):
            w = lam ** i
            num += w * (1.0 if match else 0.0)
            den += w
        return 100.0 * num / den


class PersistentTrustHistory(TrustHistory):
    """SQLite-backed variant of TrustHistory. `record` writes through to
    disk; `score` reads through on cache miss, so a subject's track
    record accumulates across process restarts (this is what lets
    trust_score climb across repeated `python demo_full_handshake.py`
    runs instead of resetting to a neutral prior every time)."""

    def __init__(self, store, k: int = K_DEFAULT):
        super().__init__(k)
        self._store = store

    def record(self, subject_id: str, accepted_without_stepup: bool) -> None:
        super().record(subject_id, accepted_without_stepup)
        self._store.record_history(subject_id, accepted_without_stepup)

    def score(self, subject_id: str, lam: float = LAMBDA_DEFAULT) -> float:
        if subject_id not in self._by_subject:
            persisted = self._store.get_history(subject_id, limit=self.k)
            if persisted:
                self._by_subject[subject_id] = deque(persisted, maxlen=self.k)
        return super().score(subject_id, lam)
