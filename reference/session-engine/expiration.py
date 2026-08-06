"""Expiration checks — RFC-0001 §5 state machine, ERR_SESSION_EXPIRED."""
from __future__ import annotations
from datetime import datetime, timezone
from generator import SessionDNA


def is_expired(sdna: SessionDNA, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now >= sdna.expires_at
