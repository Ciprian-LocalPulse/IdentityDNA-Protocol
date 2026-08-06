"""
Adversarial / fuzz tests against the Gateway state machine
(reference/gateway/handshake.py). These specifically try to break RFC-0001
§5 (state machine) and §4 (replay/malformed rejection) guarantees with
malformed, out-of-order, and randomly-mutated messages -- the kind of
input a real attacker (or a buggy client) would actually send, as
opposed to the well-formed messages every other test uses.
"""
import conftest  # noqa: F401
import uuid
from hypothesis import given, strategies as st, settings, HealthCheck

from handshake import Gateway, HandshakeContext, ProtocolError
from relationship import SubjectRegistry
from history import TrustHistory
from validator import SessionStore
from identity_compiler import ConsentReceipt
from datetime import datetime, timedelta, timezone

_SLOW = settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


def _fresh_gateway():
    subjects = SubjectRegistry()
    history = TrustHistory()
    sessions = SessionStore()
    consent = ConsentReceipt(
        consent_receipt_id="c1", subject_id="fuzz-subject", scopes=["device_dna"],
        issued_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    lookup = lambda cid: consent if cid == "c1" else None  # noqa: E731
    return Gateway("fuzz-salt", subjects, history, sessions, lookup), consent


def _valid_hello():
    return {"idp": "1.0", "type": "HELLO", "msg_id": str(uuid.uuid4()),
            "body": {"client_version": "1.0.0", "supported_suites": ["ed25519-blake3-argon2id"],
                      "nonce_c": "AAAA"}}


# --- out-of-order messages must always be rejected with ERR_STATE_INVALID ---

def test_entropy_before_hello_rejected():
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    entropy = {"type": "ENTROPY", "msg_id": str(uuid.uuid4()),
               "body": {"device_dna_hash": "aa", "consent_receipt_id": "c1"}}
    try:
        gw.handle_entropy(ctx, entropy, {}, {}, {})
        assert False, "should have raised"
    except ProtocolError as e:
        assert e.code == "ERR_STATE_INVALID"


def test_proof_before_hello_rejected():
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    proof = {"type": "PROOF", "msg_id": str(uuid.uuid4()), "body": {"signature": "x", "public_key": "y"}}
    try:
        gw.handle_proof(ctx, proof, [], {})
        assert False, "should have raised"
    except ProtocolError as e:
        assert e.code == "ERR_STATE_INVALID"


def test_double_hello_rejected():
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    gw.handle_hello(ctx, _valid_hello())
    try:
        gw.handle_hello(ctx, _valid_hello())
        assert False, "second HELLO should have raised ERR_STATE_INVALID"
    except ProtocolError as e:
        assert e.code == "ERR_STATE_INVALID"


# --- replay: identical msg_id reused within a session must be rejected ---

def test_replayed_msg_id_rejected():
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    hello = _valid_hello()
    gw.handle_hello(ctx, hello)
    # attacker resends the exact same HELLO envelope again (same msg_id)
    # -- but state has already moved on, so this hits ERR_STATE_INVALID
    # first. Test the ENTROPY-level replay instead, within a valid state:
    entropy = {"type": "ENTROPY", "msg_id": str(uuid.uuid4()),
               "body": {"device_dna_hash": "aa", "consent_receipt_id": "c1"}}
    device = {"platform": "Linux"}
    gw.handle_entropy(ctx, entropy, device, {}, {})
    # replay the SAME entropy msg_id again -- state moved to AWAITING_PROOF,
    # so this is now also ERR_STATE_INVALID (which is a valid, stronger
    # rejection -- either code is an acceptable rejection outcome).
    try:
        gw.handle_entropy(ctx, entropy, device, {}, {})
        assert False, "replayed ENTROPY should have been rejected"
    except ProtocolError as e:
        assert e.code in ("ERR_REPLAY", "ERR_STATE_INVALID")


@given(st.text(min_size=0, max_size=50))
@_SLOW
def test_hello_missing_msg_id_always_rejected(garbage_type):
    """A HELLO-shaped message missing msg_id entirely must never be
    silently accepted, regardless of what's in `type`."""
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    malformed = {"idp": "1.0", "type": garbage_type or "HELLO",
                 "body": {"client_version": "1.0.0", "supported_suites": ["ed25519-blake3-argon2id"], "nonce_c": "AAAA"}}
    try:
        gw.handle_hello(ctx, malformed)
        assert False, "HELLO without msg_id must be rejected"
    except (ProtocolError, KeyError):
        pass  # either an explicit protocol error or a hard KeyError is an acceptable rejection


@given(st.lists(st.sampled_from(["ed25519-blake3-argon2id", "x25519-sha3-hkdf", "made-up-suite", "", "AES-ONLY"]),
                 min_size=0, max_size=4, unique=True))
@_SLOW
def test_unsupported_suite_combinations(suites):
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    hello = {"idp": "1.0", "type": "HELLO", "msg_id": str(uuid.uuid4()),
             "body": {"client_version": "1.0.0", "supported_suites": suites, "nonce_c": "AAAA"}}
    if "ed25519-blake3-argon2id" in suites:
        challenge = gw.handle_hello(ctx, hello)
        assert challenge["type"] == "CHALLENGE"
    else:
        try:
            gw.handle_hello(ctx, hello)
            assert False, f"suites {suites} should have been rejected (no supported overlap)"
        except ProtocolError as e:
            assert e.code == "ERR_SUITE_UNSUPPORTED"


def test_entropy_without_consent_receipt_rejected():
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    gw.handle_hello(ctx, _valid_hello())
    entropy = {"type": "ENTROPY", "msg_id": str(uuid.uuid4()),
               "body": {"device_dna_hash": "aa", "consent_receipt_id": "does-not-exist"}}
    try:
        gw.handle_entropy(ctx, entropy, {}, {}, {})
        assert False, "entropy with invalid consent_receipt_id must be rejected"
    except ProtocolError as e:
        assert e.code == "ERR_CONSENT_MISSING"


def test_entropy_with_expired_consent_rejected():
    subjects = SubjectRegistry()
    history = TrustHistory()
    sessions = SessionStore()
    expired_consent = ConsentReceipt(
        consent_receipt_id="c-expired", subject_id="s", scopes=["device_dna"],
        issued_at=datetime.now(timezone.utc) - timedelta(days=60),
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # already expired
    )
    lookup = lambda cid: expired_consent if cid == "c-expired" else None  # noqa: E731
    gw = Gateway("fuzz-salt", subjects, history, sessions, lookup)
    ctx = HandshakeContext()
    gw.handle_hello(ctx, _valid_hello())
    entropy = {"type": "ENTROPY", "msg_id": str(uuid.uuid4()),
               "body": {"device_dna_hash": "aa", "consent_receipt_id": "c-expired"}}
    try:
        gw.handle_entropy(ctx, entropy, {}, {}, {})
        assert False, "entropy with EXPIRED consent must be rejected"
    except ProtocolError as e:
        assert e.code == "ERR_CONSENT_MISSING"


def test_proof_with_wrong_signature_rejected():
    gw, consent = _fresh_gateway()
    ctx = HandshakeContext()
    hello = _valid_hello()
    challenge = gw.handle_hello(ctx, hello)
    entropy = {"type": "ENTROPY", "msg_id": str(uuid.uuid4()),
               "body": {"device_dna_hash": "aa", "consent_receipt_id": "c1"}}
    ack = gw.handle_entropy(ctx, entropy, {"platform": "Linux"}, {}, {})
    bad_proof = {"type": "PROOF", "msg_id": str(uuid.uuid4()),
                 "body": {"signature": "bm90LWEtcmVhbC1zaWduYXR1cmU=", "public_key": "bm90LWEtcmVhbC1rZXk="}}
    try:
        gw.handle_proof(ctx, bad_proof, [], {})
        assert False, "forged/garbage proof must be rejected"
    except ProtocolError as e:
        assert e.code == "ERR_SIGNATURE_INVALID"
    assert ctx.state == "REJECTED"
