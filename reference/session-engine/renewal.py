"""
Renewal — orchestrates the VERIFY message flow (RFC-0001 §4.8): validate
the presented SDNA, then rotate and return the next generation.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validator import SessionStore  # noqa: E402
from rotator import rotate  # noqa: E402
from generator import SessionDNA  # noqa: E402


class RenewalError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def renew(store: SessionStore, session_id: str, presented_sdna: bytes) -> SessionDNA:
    ok, err = store.validate(session_id, presented_sdna)
    if not ok:
        raise RenewalError(err)
    current = store._sessions[session_id]  # reference impl; a real store would expose a safe accessor
    rotated = rotate(current)
    store.put(rotated)
    return rotated
