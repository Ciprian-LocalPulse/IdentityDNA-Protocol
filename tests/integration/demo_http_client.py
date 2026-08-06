"""
HTTP client demo — drives the FastAPI reference server (reference/server/api.py)
over real HTTP, exercising the full RFC-0001 handshake through the REST
surface instead of in-process. This is the network-level counterpart to
demo_full_handshake.py.

Prerequisite: start the server first, in a separate terminal:

    cd reference/server
    python -m uvicorn api:app --reload --port 8123

Then run this script from the repo root:

    python tests/integration/demo_http_client.py

Requires the `requests` package: pip install requests
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependency. Install it with:\n    pip install requests")
    sys.exit(1)

_REF = Path(__file__).resolve().parents[2] / "reference"
for p in ["", "identity-engine", "entropy-engine", "verifier"]:
    sys.path.insert(0, str(_REF / p) if p else str(_REF))

from verifier import ClientSession  # noqa: E402
from normalizer import normalize_device  # noqa: E402

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123"
RP_SALT = "reference-server-rp-salt-v1"  # must match reference/server/api.py's RP_SALT


def check_server_up() -> None:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(f"ERROR: could not reach {BASE_URL}.")
        print("Start the server first, in another terminal:")
        print("    cd reference/server")
        print("    python -m uvicorn api:app --reload --port 8123")
        sys.exit(1)


def run(subject_id: str = "user-http-demo") -> None:
    check_server_up()

    print(f"[1/8] POST /consent  (subject_id={subject_id})")
    r = requests.post(f"{BASE_URL}/consent", json={"subject_id": subject_id})
    r.raise_for_status()
    consent = r.json()
    print("      ->", consent)

    client = ClientSession()
    hello = client.build_hello()
    print("\n[2/8] POST /authenticate  (HELLO ->)")
    r = requests.post(f"{BASE_URL}/authenticate", json={"envelope": hello})
    r.raise_for_status()
    auth = r.json()
    handshake_id = auth["handshake_id"]
    challenge = auth["challenge"]
    print("      <- CHALLENGE", challenge["msg_id"])

    device_raw = {
        "platform": "Windows", "screen_class": "1920x1080", "timezone_offset_min": 120,
        "language": "ro", "color_depth_class": "24bit", "hardware_concurrency_class": "4-8",
        "gpu_vendor_class": "intel",
    }
    device_hash = normalize_device(device_raw, RP_SALT).hex()
    behavior_raw = {"typing_cadence_ms": [118, 122, 130, 115, 121], "pointer_entropy": 0.37}
    context_raw = {"tz_offset_min": 120, "locale": "ro-RO"}

    entropy = client.build_entropy(device_hash, behavior_raw, context_raw, consent["consent_receipt_id"])
    print("\n[3/8] POST /identity  (ENTROPY ->)")
    r = requests.post(f"{BASE_URL}/identity", json={
        "handshake_id": handshake_id, "envelope": entropy,
        "device_raw": device_raw, "behavior_raw": behavior_raw, "context_raw": context_raw,
    })
    r.raise_for_status()
    ack = r.json()["identity_ack"]
    print("      <- IDENTITY_ACK", ack["body"]["iv_digest"][:16])

    proof = client.build_proof(hello, challenge, entropy, ack)
    print("\n[4/8] POST /verify  (PROOF ->)")
    r = requests.post(f"{BASE_URL}/verify", json={
        "handshake_id": handshake_id, "envelope": proof,
        "context_priors": [0.9, 0.85],
        "risk_context": {"attempts_last_minute": 1, "ip_reputation_score": 90},
    })
    r.raise_for_status()
    result = r.json()
    print("      <- TRUST_RESULT")
    print(json.dumps(result["trust_result"]["body"], indent=8))

    sdna = result.get("session_dna")
    if sdna is None:
        print("\n(No SESSION_DNA — decision was DENY. Run this script again to")
        print(" see the trust score improve, same as the CLI persistence demo.)")
        return

    sdna_body = sdna["body"]
    print("\n[5/8] SESSION_DNA issued:", sdna_body["session_id"])

    print("\n[6/8] POST /renew  (rotate SDNA)")
    r = requests.post(f"{BASE_URL}/renew", json={
        "session_id": sdna_body["session_id"], "sdna_b64": sdna_body["sdna"],
    })
    r.raise_for_status()
    print("      ->", r.json())

    print("\n[7/8] GET /session/{id}")
    r = requests.get(f"{BASE_URL}/session/{sdna_body['session_id']}")
    r.raise_for_status()
    print("      ->", r.json())

    print("\n[8/8] DELETE /session/{id}  (revoke)")
    r = requests.delete(f"{BASE_URL}/session/{sdna_body['session_id']}")
    r.raise_for_status()
    print("      ->", r.json())

    print("\nHTTP handshake demo completed successfully.")


if __name__ == "__main__":
    run()
