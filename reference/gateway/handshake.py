"""
Gateway — orchestrates the full IDP handshake (RFC-0001 §3-§9) end to
end by wiring together crypto, entropy-engine, identity-engine,
trust-engine, and session-engine. This is the reference "server side"
orchestration used by reference/server/api.py and by the CLI's
`identitydna verify` command, and by tests/unit/test_handshake.py.

It exists so the nine wire messages of RFC-0001 §4 have one obvious,
readable call path instead of being reimplemented ad hoc by every
consumer.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

_REF = Path(__file__).resolve().parents[1]
for p in [_REF, _REF / "identity-engine", _REF / "trust-engine", _REF / "session-engine", _REF / "entropy-engine"]:
    sys.path.insert(0, str(p))

from crypto import canonical_json, hash_blake3, SigningKeyPair, EphemeralKeyPair  # noqa: E402
from identity_compiler import IdentityCompiler, ConsentReceipt, ConsentMissingError  # noqa: E402
from relationship import SubjectRegistry  # noqa: E402
from verification import verify_proof  # noqa: E402
from score import compute_trust_score  # noqa: E402
from weights import DEFAULT_WEIGHTS  # noqa: E402
from policies import DEFAULT_POLICY, Decision  # noqa: E402
from history import TrustHistory  # noqa: E402
from generator import generate_initial_sdna, ROTATION_INTERVAL_S_DEFAULT  # noqa: E402
from validator import SessionStore  # noqa: E402


class ProtocolError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class HandshakeContext:
    """Server-side mutable state for one in-flight handshake attempt.
    Mirrors the state machine in RFC-0001 §5."""
    state: str = "NEW"
    server_nonce: bytes | None = None
    server_eph: EphemeralKeyPair | None = None
    hello_msg: dict | None = None
    challenge_msg: dict | None = None
    entropy_msg: dict | None = None
    identity_ack_msg: dict | None = None
    seen_msg_ids: set = field(default_factory=set)


class Gateway:
    def __init__(self, rp_salt: str, subject_registry: SubjectRegistry,
                 trust_history: TrustHistory, session_store: SessionStore,
                 consent_lookup):
        """`consent_lookup` is a callable: consent_receipt_id -> ConsentReceipt | None,
        modeling the consent-record store (RFC-0001 §10.2)."""
        self.compiler = IdentityCompiler(rp_salt=rp_salt)
        self.subjects = subject_registry
        self.history = trust_history
        self.sessions = session_store
        self.consent_lookup = consent_lookup

    def _check_msg_id(self, ctx: HandshakeContext, msg: dict) -> None:
        mid = msg.get("msg_id") or msg.get("body", {}).get("msg_id")
        # In this reference implementation msg_id lives on the envelope;
        # callers constructing envelopes must supply one (RFC-0001 §4).
        if mid is None:
            raise ProtocolError("ERR_MALFORMED", "missing msg_id")
        if mid in ctx.seen_msg_ids:
            raise ProtocolError("ERR_REPLAY", mid)
        ctx.seen_msg_ids.add(mid)

    def handle_hello(self, ctx: HandshakeContext, hello_envelope: dict) -> dict:
        if ctx.state != "NEW":
            raise ProtocolError("ERR_STATE_INVALID", ctx.state)
        self._check_msg_id(ctx, hello_envelope)
        body = hello_envelope["body"]
        if "ed25519-blake3-argon2id" not in body.get("supported_suites", []):
            raise ProtocolError("ERR_SUITE_UNSUPPORTED")

        from crypto.primitives import csprng_bytes
        import base64
        ctx.server_nonce = csprng_bytes(32)
        ctx.server_eph = EphemeralKeyPair.generate()
        ctx.hello_msg = hello_envelope
        challenge_body = {
            "selected_suite": "ed25519-blake3-argon2id",
            "server_nonce": base64.b64encode(ctx.server_nonce).decode(),
            "challenge": base64.b64encode(csprng_bytes(32)).decode(),
            "difficulty": 0,
            "server_eph_public": ctx.server_eph.public_key_b64,
        }
        ctx.challenge_msg = {"type": "CHALLENGE", "msg_id": str(uuid.uuid4()), "body": challenge_body}
        ctx.state = "CHALLENGED"
        return ctx.challenge_msg

    def handle_entropy(self, ctx: HandshakeContext, entropy_envelope: dict,
                        device_raw: dict, behavior_raw: dict, context_raw: dict) -> dict:
        if ctx.state != "CHALLENGED":
            raise ProtocolError("ERR_STATE_INVALID", ctx.state)
        self._check_msg_id(ctx, entropy_envelope)
        body = entropy_envelope["body"]

        consent = self.consent_lookup(body.get("consent_receipt_id"))
        if consent is None or not consent.is_valid():
            raise ProtocolError("ERR_CONSENT_MISSING")

        iv = self.compiler.compile(device_raw, behavior_raw, context_raw, consent)
        ctx.entropy_msg = entropy_envelope
        ctx.identity_ack_msg = {
            "type": "IDENTITY_ACK",
            "msg_id": str(uuid.uuid4()),
            "body": {"identity_vector_id": iv.identity_vector_id, "iv_digest": iv.iv_digest},
        }
        ctx._iv = iv  # stashed for the PROOF step (not part of the wire message)
        ctx._subject_id = consent.subject_id
        ctx.state = "AWAITING_PROOF"
        return ctx.identity_ack_msg

    def handle_proof(self, ctx: HandshakeContext, proof_envelope: dict,
                      context_priors: list[float], risk_context: dict[str, Any]) -> dict:
        if ctx.state != "AWAITING_PROOF":
            raise ProtocolError("ERR_STATE_INVALID", ctx.state)
        self._check_msg_id(ctx, proof_envelope)
        body = proof_envelope["body"]

        ok, transcript_hash = verify_proof(
            ctx.hello_msg, ctx.challenge_msg, ctx.entropy_msg, ctx.identity_ack_msg,
            body["public_key"], body["signature"],
        )
        if not ok:
            ctx.state = "REJECTED"
            raise ProtocolError("ERR_SIGNATURE_INVALID")

        ctx.state = "VERIFYING"
        subject_id = ctx._subject_id
        distance = self.subjects.relationship_distance(subject_id, ctx._iv)
        n_eff = 3  # device + behavior + context layers all present in this reference flow

        # Bootstrap rule (not in RFC-0001 normative text, reference-impl
        # policy choice): a subject with NO enrolled baseline yet cannot
        # be identity-scored against anything, by definition. We still
        # enroll their first observed vector as the baseline regardless
        # of this session's trust decision -- otherwise a subject whose
        # very first session scores below ALLOW/STEP_UP would never
        # accumulate the baseline needed to ever improve, an unrecoverable
        # cold-start deadlock. This mirrors real-world enrollment flows
        # (e.g. a separate, more heavily-verified onboarding step) being
        # out of scope for this reference handshake.
        first_ever_session = not self.subjects.has_baseline(subject_id)
        if first_ever_session:
            self.subjects.enroll(subject_id, ctx._iv)

        result = compute_trust_score(
            identity_distance=distance,
            n_eff=n_eff,
            subject_id=subject_id,
            history=self.history,
            context_priors=context_priors,
            risk_context=risk_context,
        )

        trust_msg = {
            "type": "TRUST_RESULT",
            "msg_id": str(uuid.uuid4()),
            "body": {
                "trust_score": result.trust_score,
                "decision": result.decision.value,
                "risk_flags": result.risk_flags,
                "components": result.components,
            },
        }

        if result.decision == Decision.DENY:
            ctx.state = "DENIED"
            # formal-model.md §3.3.1: a first-ever (no-baseline) session is
            # never recorded into history -- it isn't yet a meaningful
            # judgment of identity consistency, and recording it as a
            # failure would create a permanent-lockout deadlock.
            if not first_ever_session:
                self.history.record(subject_id, False)
            return trust_msg

        ctx.state = "TRUST_EVALUATED"
        # match(t-k) = 1 for ALLOW or STEP_UP (§3.3.1) -- only an outright
        # DENY (handled above) counts as a history failure.
        if not first_ever_session:
            self.history.record(subject_id, True)
        if result.decision == Decision.ALLOW:
            self.subjects.update_baseline_ewma(subject_id, ctx._iv)
        elif not self.subjects.has_baseline(subject_id):
            self.subjects.enroll(subject_id, ctx._iv)

        client_eph_pub = ctx.hello_msg["body"].get("client_eph_public") or body["public_key"]
        sdna = generate_initial_sdna(
            server_eph=ctx.server_eph,
            client_public_b64=client_eph_pub,
            transcript_hash=transcript_hash,
        )
        self.sessions.put(sdna)
        ctx.state = "ACTIVE"
        ctx._sdna_msg = {
            "type": "SESSION_DNA",
            "msg_id": str(uuid.uuid4()),
            "body": {
                "session_id": sdna.session_id,
                "sdna": sdna.sdna_b64,
                "issued_at": sdna.issued_at.isoformat(),
                "expires_at": sdna.expires_at.isoformat(),
                "rotation_interval_s": sdna.rotation_interval_s,
            },
        }
        ctx._trust_msg = trust_msg
        return trust_msg

    def session_dna_message(self, ctx: HandshakeContext) -> dict | None:
        return getattr(ctx, "_sdna_msg", None)
