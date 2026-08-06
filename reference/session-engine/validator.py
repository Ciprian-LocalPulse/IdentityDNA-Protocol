"""
Session validator — enforces RFC-0001 §9's "no session DNA reuse window"
rule: a generation once superseded by rotation is permanently invalid,
even if not yet time-expired.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generator import SessionDNA  # noqa: E402
from expiration import is_expired  # noqa: E402


class SessionStore:
    """Reference in-memory store: session_id -> (current SessionDNA, revoked flag).
    Production deployments MUST use a store with TTL-based eviction and
    MUST NOT allow lookups to leak timing information about validity
    (out of scope for this reference implementation's simplicity)."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionDNA] = {}
        self._revoked: set[str] = set()

    def put(self, sdna: SessionDNA) -> None:
        self._sessions[sdna.session_id] = sdna

    def revoke(self, session_id: str) -> None:
        self._revoked.add(session_id)

    def validate(self, session_id: str, presented_sdna: bytes) -> tuple[bool, str]:
        """Returns (is_valid, error_code_or_empty)."""
        if session_id in self._revoked:
            return False, "ERR_SESSION_REVOKED"
        current = self._sessions.get(session_id)
        if current is None:
            return False, "ERR_SESSION_EXPIRED"
        if is_expired(current):
            return False, "ERR_SESSION_EXPIRED"
        if presented_sdna != current.sdna:
            # Either a stale (superseded) generation or a forged value.
            return False, "ERR_SESSION_EXPIRED"
        return True, ""
