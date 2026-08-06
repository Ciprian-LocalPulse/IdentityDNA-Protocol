"""
Session DNA rotation — RFC-0001 §9:

    SDNA_(k+1) = HKDF(ikm = SDNA_k, salt = rotation_nonce_k, info = "IDP-ROTATE-v1", L = 32)

Because HKDF is one-way, SDNA_k cannot be recovered from SDNA_(k+1)
(forward secrecy across rotations); a superseded SDNA_k MUST be rejected
by validator.py once rotation has occurred.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto import hkdf, csprng_bytes  # noqa: E402
from generator import SessionDNA  # noqa: E402


def rotate(current: SessionDNA) -> SessionDNA:
    rotation_nonce = csprng_bytes(16)
    new_sdna = hkdf(ikm=current.sdna, salt=rotation_nonce, info="IDP-ROTATE-v1", length=32)
    now = datetime.now(timezone.utc)
    return SessionDNA(
        session_id=current.session_id,
        sdna=new_sdna,
        generation=current.generation + 1,
        issued_at=now,
        expires_at=now + timedelta(seconds=current.rotation_interval_s),
        rotation_interval_s=current.rotation_interval_s,
    )
