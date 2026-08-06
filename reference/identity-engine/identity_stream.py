"""
Identity Stream — the time-ordered sequence of Identity Vectors produced
during a session (RFC-0001 §2, Terminology; used by trust_engine/history.py
and trust_engine/score.py for S_history / behavioral drift detection).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from identity_vector import IdentityVector


@dataclass
class StreamSample:
    identity_vector: IdentityVector
    captured_at: str  # RFC-3339


@dataclass
class IdentityStream:
    session_id: str
    samples: list[StreamSample] = field(default_factory=list)

    def append(self, iv: IdentityVector) -> None:
        self.samples.append(StreamSample(
            identity_vector=iv,
            captured_at=datetime.now(timezone.utc).isoformat(),
        ))

    def latest(self) -> IdentityVector | None:
        return self.samples[-1].identity_vector if self.samples else None

    def drift_series(self) -> list[float]:
        """Consecutive-sample distances — used by trust_engine risk rules
        to detect abrupt behavioral/device drift mid-session
        (threat-model.md §3.6, Device Theft mitigation)."""
        out = []
        for a, b in zip(self.samples, self.samples[1:]):
            out.append(a.identity_vector.distance(b.identity_vector))
        return out

    def baseline(self) -> IdentityVector | None:
        """The first sample of a session is treated as the enrollment/
        reference baseline for that session (formal-model.md §3.2 refers
        to a longer-lived IV_baseline across sessions; the reference
        implementation's TrustHistory, not IdentityStream, owns that
        cross-session baseline — see trust_engine/history.py)."""
        return self.samples[0].identity_vector if self.samples else None
