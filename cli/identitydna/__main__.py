"""
IdentityDNA Protocol CLI.

Implements the command set from RFC-0001 / the repository ROADMAP:
    identitydna login       - run a full demo handshake locally
    identitydna verify      - verify a session's SDNA against the store
    identitydna compile     - compile an Identity Vector from a JSON input file
    identitydna inspect     - pretty-print a message envelope's transcript hash
    identitydna generate    - generate a fresh Ed25519/X25519 keypair
    identitydna session     - inspect an in-memory demo session's lifecycle
    identitydna trust       - run the Trust Engine against a JSON context file
    identitydna benchmark   - micro-benchmark core primitives (see benchmarks/)

Install: `pip install -e .` from the cli/ directory (see cli/README.md),
or run directly: `python3 -m identitydna <command>` from the cli/ folder.
"""
from __future__ import annotations

import json
import sys
import base64
import time
from pathlib import Path

import click

_REF = Path(__file__).resolve().parents[2] / "reference"
for p in ["", "identity-engine", "trust-engine", "session-engine", "entropy-engine", "gateway", "verifier", "storage"]:
    sys.path.insert(0, str(_REF / p) if p else str(_REF))


@click.group()
@click.version_option(version="1.0.0-draft", prog_name="identitydna")
def cli():
    """IdentityDNA Protocol (IDP) reference CLI."""
    pass


@cli.command()
@click.option("--verbose/--quiet", default=True)
@click.option("--persist/--no-persist", default=True,
              help="Use the SQLite-backed subject registry/history (default) vs. pure in-memory (always first-session).")
def login(verbose, persist):
    """Run a complete local demo handshake (client + server in-process).
    With --persist (default), repeated runs for the same demo subject
    accumulate trust history and an enrolled baseline, so trust_score
    should climb across successive invocations."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "integration"))
    from demo_full_handshake import run_demo
    result = run_demo(verbose=verbose, persist=persist)
    click.echo(json.dumps({
        "final_state": result["final_state"],
        "trust_result": result["trust_result"]["body"],
    }, indent=2))


@cli.command()
@click.option("--subject-id", default=None, help="Reset only this subject; omit to wipe all stored state.")
def reset(subject_id):
    """Wipe the persisted SQLite state (RFC-0001 §10.5 deletion mechanism,
    simplified). Use this to reproduce a clean 'first session' demo."""
    from sqlite_store import SQLiteStore, DEFAULT_DB_PATH
    store = SQLiteStore(DEFAULT_DB_PATH)
    store.reset(subject_id)
    click.echo(json.dumps({"status": "reset", "subject_id": subject_id or "ALL", "db_path": str(store.db_path)}, indent=2))


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
def compile(input_file):
    """Compile an Identity Vector from a JSON file with
    {"device": {...}, "behavior": {...}, "context": {...}, "rp_salt": "..."}"""
    from identity_vector import compile_identity_vector
    data = json.loads(Path(input_file).read_text())
    iv = compile_identity_vector(
        data["device"], data["behavior"], data["context"], data.get("rp_salt", "default-salt")
    )
    click.echo(json.dumps({
        "identity_vector_id": iv.identity_vector_id,
        "iv_digest": iv.iv_digest,
        "dimension": len(iv.vector),
    }, indent=2))


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
def trust(input_file):
    """Run the Trust Engine against a JSON context file. See
    docs/specification/messages/trust-score.md for the expected schema."""
    from score import compute_trust_score
    from history import TrustHistory
    data = json.loads(Path(input_file).read_text())
    hist = TrustHistory()
    result = compute_trust_score(
        identity_distance=data.get("identity_distance"),
        n_eff=data.get("n_eff", 3),
        subject_id=data.get("subject_id", "anonymous"),
        history=hist,
        context_priors=data.get("context_priors", []),
        risk_context=data.get("risk_context", {}),
    )
    click.echo(json.dumps({
        "trust_score": result.trust_score,
        "decision": result.decision.value,
        "risk_flags": result.risk_flags,
        "components": result.components,
    }, indent=2))


@cli.command()
def generate():
    """Generate a fresh Ed25519 signing keypair and X25519 ephemeral keypair."""
    from crypto import SigningKeyPair, EphemeralKeyPair
    sk = SigningKeyPair.generate()
    eph = EphemeralKeyPair.generate()
    click.echo(json.dumps({
        "ed25519_public_key": sk.public_key_b64,
        "x25519_ephemeral_public_key": eph.public_key_b64,
        "note": "Private key material is not printed. This command is for demo/testing only.",
    }, indent=2))


@cli.command()
@click.argument("envelope_file", type=click.Path(exists=True))
def inspect(envelope_file):
    """Pretty-print a message envelope and validate it against the
    RFC-0001 §4 envelope schema (idp, type, msg_id, ts, body)."""
    data = json.loads(Path(envelope_file).read_text())
    required = {"idp", "type", "msg_id", "body"}
    missing = required - data.keys()
    status = "VALID" if not missing else f"MALFORMED (missing: {sorted(missing)})"
    click.echo(json.dumps({"status": status, "envelope": data}, indent=2))


@cli.command()
def session():
    """Demonstrate the session lifecycle: generate -> rotate -> expire check."""
    from crypto import EphemeralKeyPair
    from generator import generate_initial_sdna
    from rotator import rotate
    from expiration import is_expired

    server_eph = EphemeralKeyPair.generate()
    client_eph = EphemeralKeyPair.generate()
    sdna0 = generate_initial_sdna(server_eph, client_eph.public_key_b64, b"demo-transcript-hash-32-bytes!!")
    sdna1 = rotate(sdna0)

    click.echo(json.dumps({
        "generation_0": {"session_id": sdna0.session_id, "sdna": sdna0.sdna_b64[:16] + "...", "expires_at": sdna0.issued_at.isoformat()},
        "generation_1_after_rotation": {"sdna": sdna1.sdna_b64[:16] + "...", "generation": sdna1.generation},
        "generation_0_expired_now": is_expired(sdna0),
    }, indent=2))


@cli.command()
@click.option("--iterations", default=1000, show_default=True)
def benchmark(iterations):
    """Micro-benchmark the hot-path primitives (hashing, HKDF, signing)."""
    from crypto import hash_blake3, hkdf, SigningKeyPair, csprng_bytes

    sk = SigningKeyPair.generate()
    payload = csprng_bytes(64)

    t0 = time.perf_counter()
    for _ in range(iterations):
        hash_blake3(payload, domain="IDP-BENCH-v1")
    t_hash = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(iterations):
        hkdf(payload, salt=b"salt", info="IDP-BENCH-v1", length=32)
    t_hkdf = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(iterations):
        sk.sign(payload)
    t_sign = time.perf_counter() - t0

    click.echo(json.dumps({
        "iterations": iterations,
        "hash_blake3_ops_per_sec": round(iterations / t_hash, 1),
        "hkdf_ops_per_sec": round(iterations / t_hkdf, 1),
        "ed25519_sign_ops_per_sec": round(iterations / t_sign, 1),
    }, indent=2))


if __name__ == "__main__":
    cli()
