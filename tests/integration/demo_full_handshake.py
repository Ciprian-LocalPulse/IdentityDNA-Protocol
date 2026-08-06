"""
End-to-end demo: runs the complete IDP handshake (RFC-0001 §3) using the
reference implementation, client and server both in-process. This is the
executable proof that identity-engine + trust-engine + session-engine +
gateway/verifier actually interoperate, not just import cleanly.

Run: python3 tests/integration/demo_full_handshake.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

_REF = Path(__file__).resolve().parents[2] / "reference"
for p in ["", "identity-engine", "trust-engine", "session-engine", "entropy-engine", "gateway", "verifier"]:
    sys.path.insert(0, str(_REF / p) if p else str(_REF))

from handshake import Gateway, HandshakeContext, ProtocolError  # noqa: E402
from verifier import ClientSession  # noqa: E402
from relationship import SubjectRegistry, PersistentSubjectRegistry  # noqa: E402
from history import TrustHistory, PersistentTrustHistory  # noqa: E402
from validator import SessionStore  # noqa: E402
from identity_compiler import ConsentReceipt  # noqa: E402
from normalizer import normalize_device  # noqa: E402

sys.path.insert(0, str(_REF / "storage"))
from sqlite_store import SQLiteStore, DEFAULT_DB_PATH  # noqa: E402


def run_demo(verbose: bool = True, persist: bool = True, db_path=None) -> dict:
    """`persist=True` (default) uses a SQLite-backed subject registry and
    trust history at `db_path` (default: ~/.identitydna/identitydna_demo.db),
    so running this script repeatedly for the SAME subject_id accumulates
    real history and an enrolled baseline — trust_score should climb on
    successive runs instead of resetting every time. Pass persist=False
    (or a fresh db_path) to reproduce the original always-first-session
    behavior."""
    if persist:
        store = SQLiteStore(db_path or DEFAULT_DB_PATH)
        subjects = PersistentSubjectRegistry(store)
        history = PersistentTrustHistory(store)
        if verbose:
            print(f"[persistence] using {store.db_path}")
    else:
        subjects = SubjectRegistry()
        history = TrustHistory()
    sessions = SessionStore()

    subject_id = "user-alice"
    consent = ConsentReceipt(
        consent_receipt_id="consent-001",
        subject_id=subject_id,
        scopes=["device_dna"],
        issued_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    consent_lookup = lambda cid: consent if cid == consent.consent_receipt_id else None  # noqa: E731

    gw = Gateway(rp_salt="demo-rp-salt-v1", subject_registry=subjects,
                 trust_history=history, session_store=sessions, consent_lookup=consent_lookup)

    client = ClientSession()
    ctx = HandshakeContext()

    device_raw = {
        "platform": "Linux", "screen_class": "1920x1080", "timezone_offset_min": 120,
        "language": "ro", "color_depth_class": "24bit", "hardware_concurrency_class": "4-8",
        "gpu_vendor_class": "intel",
    }
    device_hash = normalize_device(device_raw, "demo-rp-salt-v1").hex()
    behavior_raw = {"typing_cadence_ms": [118, 122, 130, 115, 121], "pointer_entropy": 0.37}
    context_raw = {"tz_offset_min": 120, "locale": "ro-RO"}

    # 1. HELLO
    hello = client.build_hello()
    if verbose: print("-> HELLO", hello["msg_id"])

    # 2. CHALLENGE
    challenge = gw.handle_hello(ctx, hello)
    if verbose: print("<- CHALLENGE", challenge["msg_id"], "state=", ctx.state)

    # 3. ENTROPY
    entropy = client.build_entropy(device_hash, behavior_raw, context_raw, consent.consent_receipt_id)
    if verbose: print("-> ENTROPY", entropy["msg_id"])

    # 4. IDENTITY_ACK
    identity_ack = gw.handle_entropy(ctx, entropy, device_raw, behavior_raw, context_raw)
    if verbose: print("<- IDENTITY_ACK", identity_ack["body"]["iv_digest"][:16], "state=", ctx.state)

    # 5. PROOF
    proof = client.build_proof(hello, challenge, entropy, identity_ack)
    if verbose: print("-> PROOF", proof["msg_id"])

    # 6. TRUST_RESULT (+ SESSION_DNA generated server-side)
    trust_result = gw.handle_proof(
        ctx, proof,
        context_priors=[0.95, 0.9],
        risk_context={"attempts_last_minute": 1, "ip_reputation_score": 92},
    )
    if verbose:
        print("<- TRUST_RESULT", trust_result["body"], "state=", ctx.state)

    sdna_msg = gw.session_dna_message(ctx)
    if verbose and sdna_msg:
        print("<- SESSION_DNA", sdna_msg["body"]["session_id"], "state=", ctx.state)

    return {"trust_result": trust_result, "session_dna": sdna_msg, "final_state": ctx.state}


if __name__ == "__main__":
    result = run_demo()
    assert result["final_state"] in ("ACTIVE", "DENIED"), f"unexpected final state {result['final_state']}"
    print("\nDemo completed. Final state:", result["final_state"])
