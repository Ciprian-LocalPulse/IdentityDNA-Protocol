"""
Session DNA generator — RFC-0001 §9:

    SDNA_0 = HKDF(ikm = ECDH(client_eph, server_eph), salt = transcript_hash,
                  info = "IDP-SESSION-DNA-v1", L = 32)
"""
from __future__ import annotations

import sys
import uuid
import base64
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto import hkdf, ecdh_shared_secret, EphemeralKeyPair  # noqa: E402

ROTATION_INTERVAL_S_DEFAULT = 300


@dataclass
class SessionDNA:
    session_id: str
    sdna: bytes
    generation: int
    issued_at: datetime
    expires_at: datetime
    rotation_interval_s: int

    @property
    def sdna_b64(self) -> str:
        return base64.b64encode(self.sdna).decode("ascii")


def generate_initial_sdna(
    server_eph: EphemeralKeyPair,
    client_public_b64: str,
    transcript_hash: bytes,
    rotation_interval_s: int = ROTATION_INTERVAL_S_DEFAULT,
) -> SessionDNA:
    """Server-side derivation: only the server's own ephemeral private key
    and the client's ephemeral public key are needed for ECDH (RFC-0001 §9).
    The client independently derives the same SDNA_0 using its own private
    key and the server's public key from CHALLENGE — standard ECDH symmetry."""
    shared = ecdh_shared_secret(server_eph, client_public_b64)
    sdna = hkdf(ikm=shared, salt=transcript_hash, info="IDP-SESSION-DNA-v1", length=32)
    now = datetime.now(timezone.utc)
    return SessionDNA(
        session_id=str(uuid.uuid4()),
        sdna=sdna,
        generation=0,
        issued_at=now,
        expires_at=now + timedelta(seconds=rotation_interval_s),
        rotation_interval_s=rotation_interval_s,
    )
