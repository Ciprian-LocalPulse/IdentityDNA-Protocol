"""
Reference Server API — implements the REST surface listed in RFC-0001's
companion component table:

    POST   /authenticate   - start a handshake (HELLO -> CHALLENGE)
    POST   /verify         - submit ENTROPY+PROOF, get TRUST_RESULT/SESSION_DNA
    POST   /renew          - VERIFY message equivalent (rotate SDNA)
    POST   /trust          - inspect trust score for an ad-hoc context (debug/testing)
    POST   /identity       - compile an Identity Vector standalone (debug/testing)
    GET    /session/{id}   - inspect session metadata (no secret material returned)
    DELETE /session/{id}   - REVOKE

This is a reference/demo server (in-memory state, single process). It is
NOT hardened for production deployment (no persistence, no auth on the
debug endpoints, no rate limiting middleware wired in — see
threat-model.md §3.3 for what a production deployment MUST add).

Run: uvicorn api:app --reload   (from reference/server/)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_REF = Path(__file__).resolve().parents[1]
for p in ["", "identity-engine", "trust-engine", "session-engine", "entropy-engine", "gateway", "verifier"]:
    sys.path.insert(0, str(_REF / p) if p else str(_REF))

from handshake import Gateway, HandshakeContext, ProtocolError  # noqa: E402
from relationship import SubjectRegistry, PersistentSubjectRegistry  # noqa: E402
from history import TrustHistory, PersistentTrustHistory  # noqa: E402
from validator import SessionStore  # noqa: E402
from identity_compiler import ConsentReceipt  # noqa: E402
from identity_vector import compile_identity_vector  # noqa: E402
from score import compute_trust_score  # noqa: E402

sys.path.insert(0, str(_REF / "storage"))
from sqlite_store import SQLiteStore, DEFAULT_DB_PATH  # noqa: E402

app = FastAPI(
    title="IdentityDNA Protocol — Reference Server",
    version="1.0.0-draft",
    description="Reference implementation of RFC-0001. Not for production use.",
)

# --- state (SQLite-backed by default, see storage/sqlite_store.py) ---
# Set IDP_PERSIST=0 in the environment to fall back to pure in-memory
# state (always-first-session behavior, useful for isolated testing).
import os as _os
_PERSIST = _os.environ.get("IDP_PERSIST", "1") != "0"
if _PERSIST:
    _store = SQLiteStore(DEFAULT_DB_PATH)
    _subjects = PersistentSubjectRegistry(_store)
    _history = PersistentTrustHistory(_store)
else:
    _subjects = SubjectRegistry()
    _history = TrustHistory()
_sessions = SessionStore()
_consents: dict[str, ConsentReceipt] = {}
_handshakes: dict[str, HandshakeContext] = {}

RP_SALT = "reference-server-rp-salt-v1"


def _consent_lookup(cid: Optional[str]) -> Optional[ConsentReceipt]:
    return _consents.get(cid) if cid else None


_gateway = Gateway(RP_SALT, _subjects, _history, _sessions, _consent_lookup)


class HelloRequest(BaseModel):
    envelope: dict[str, Any]


class EntropyRequest(BaseModel):
    handshake_id: str
    envelope: dict[str, Any]
    device_raw: dict[str, Any]
    behavior_raw: dict[str, Any]
    context_raw: dict[str, Any]


class ProofRequest(BaseModel):
    handshake_id: str
    envelope: dict[str, Any]
    context_priors: list[float] = []
    risk_context: dict[str, Any] = {}


class RenewRequest(BaseModel):
    session_id: str
    sdna_b64: str


class TrustDebugRequest(BaseModel):
    identity_distance: Optional[float] = None
    n_eff: int = 3
    subject_id: str = "debug-subject"
    context_priors: list[float] = []
    risk_context: dict[str, Any] = {}


class IdentityDebugRequest(BaseModel):
    device: dict[str, Any]
    behavior: dict[str, Any]
    context: dict[str, Any]


class ConsentRequest(BaseModel):
    subject_id: str
    scopes: list[str] = ["device_dna"]
    ttl_days: int = 30


@app.post("/consent", tags=["setup"])
def create_consent(req: ConsentRequest):
    """Demo-only helper to mint a consent receipt (RFC-0001 §10.2). A
    production deployment issues these from an actual consent-capture UI."""
    receipt = ConsentReceipt(
        consent_receipt_id=str(uuid.uuid4()),
        subject_id=req.subject_id,
        scopes=req.scopes,
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=req.ttl_days),
    )
    _consents[receipt.consent_receipt_id] = receipt
    return {"consent_receipt_id": receipt.consent_receipt_id, "expires_at": receipt.expires_at.isoformat()}


@app.post("/authenticate", tags=["handshake"])
def authenticate(req: HelloRequest):
    handshake_id = str(uuid.uuid4())
    ctx = HandshakeContext()
    try:
        challenge = _gateway.handle_hello(ctx, req.envelope)
    except ProtocolError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "detail": e.detail})
    _handshakes[handshake_id] = ctx
    return {"handshake_id": handshake_id, "challenge": challenge}


@app.post("/identity", tags=["handshake"])
def submit_entropy(req: EntropyRequest):
    ctx = _handshakes.get(req.handshake_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail={"code": "ERR_STATE_INVALID", "detail": "unknown handshake_id"})
    try:
        ack = _gateway.handle_entropy(ctx, req.envelope, req.device_raw, req.behavior_raw, req.context_raw)
    except ProtocolError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "detail": e.detail})
    return {"identity_ack": ack}


@app.post("/verify", tags=["handshake"])
def submit_proof(req: ProofRequest):
    ctx = _handshakes.get(req.handshake_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail={"code": "ERR_STATE_INVALID", "detail": "unknown handshake_id"})
    try:
        trust_result = _gateway.handle_proof(ctx, req.envelope, req.context_priors, req.risk_context)
    except ProtocolError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "detail": e.detail})
    sdna_msg = _gateway.session_dna_message(ctx)
    return {"trust_result": trust_result, "session_dna": sdna_msg}


@app.post("/renew", tags=["session"])
def renew_session(req: RenewRequest):
    import base64
    sys.path.insert(0, str(_REF / "session-engine"))
    from renewal import renew, RenewalError
    try:
        rotated = renew(_sessions, req.session_id, base64.b64decode(req.sdna_b64))
    except RenewalError as e:
        raise HTTPException(status_code=400, detail={"code": e.code})
    return {
        "session_id": rotated.session_id,
        "sdna": rotated.sdna_b64,
        "generation": rotated.generation,
        "expires_at": rotated.expires_at.isoformat(),
    }


@app.get("/session/{session_id}", tags=["session"])
def get_session(session_id: str):
    current = _sessions._sessions.get(session_id)  # reference impl direct access
    if current is None:
        raise HTTPException(status_code=404, detail={"code": "ERR_SESSION_EXPIRED"})
    return {
        "session_id": current.session_id,
        "generation": current.generation,
        "issued_at": current.issued_at.isoformat(),
        "expires_at": current.expires_at.isoformat(),
        # sdna itself intentionally NOT returned — this is an inspection
        # endpoint, not a credential-retrieval endpoint.
    }


@app.delete("/session/{session_id}", tags=["session"])
def revoke_session(session_id: str):
    _sessions.revoke(session_id)
    return {"session_id": session_id, "status": "REVOKED"}


@app.post("/trust", tags=["debug"])
def debug_trust(req: TrustDebugRequest):
    """Non-normative debug endpoint: run the Trust Engine on an arbitrary
    context without a full handshake, for testing policy tuning."""
    result = compute_trust_score(
        identity_distance=req.identity_distance,
        n_eff=req.n_eff,
        subject_id=req.subject_id,
        history=_history,
        context_priors=req.context_priors,
        risk_context=req.risk_context,
    )
    return {
        "trust_score": result.trust_score,
        "decision": result.decision.value,
        "risk_flags": result.risk_flags,
        "components": result.components,
    }


@app.post("/identity/compile", tags=["debug"])
def debug_identity(req: IdentityDebugRequest):
    """Non-normative debug endpoint: compile an Identity Vector directly
    (bypasses consent gating — for local testing only, never expose this
    unauthenticated in production)."""
    iv = compile_identity_vector(req.device, req.behavior, req.context, RP_SALT)
    return {"identity_vector_id": iv.identity_vector_id, "iv_digest": iv.iv_digest, "dimension": len(iv.vector)}


@app.post("/debug/reset", tags=["debug"])
def debug_reset(subject_id: Optional[str] = None):
    """Wipe persisted SQLite state for a subject (or all subjects if
    omitted). Mirrors `identitydna reset`. Reference/debug only — a
    production deployment MUST NOT expose an unauthenticated reset
    endpoint."""
    if _PERSIST:
        _store.reset(subject_id)
    return {"status": "reset", "subject_id": subject_id or "ALL", "persisted": _PERSIST}


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "protocol_version": "1.0.0-draft", "persistence": _PERSIST}
