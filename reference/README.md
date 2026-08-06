# IdentityDNA Protocol — Reference Implementation

This directory contains a **functional Phase-1 reference implementation**
of RFC-0001 (`docs/protocol/RFC-0001-IdentityDNA-Protocol.md`). It is a
reference/demo implementation, not a hardened production system — see
each module's docstring and `docs/architecture/threat-model.md` for what
a production deployment must add.

## Layout

| Directory | Implements |
|---|---|
| `crypto/` | RFC-0001 §11 — hashing, signatures, ECDH, HKDF, AEAD, CSPRNG |
| `entropy-engine/` | Device/behavior/context normalization (RFC-0001 §10) |
| `identity-engine/` | Identity Vector compilation, streams, consent gating, cross-session relationships |
| `trust-engine/` | Trust Score computation (formal-model.md §3): weights, history, risk rules, policies, confidence |
| `session-engine/` | Session DNA generation, rotation, expiration, validation, renewal (RFC-0001 §9) |
| `gateway/` | Server-side handshake orchestration (RFC-0001 §3-§9), the state machine |
| `verifier/` | Client-side handshake helper (builds HELLO/ENTROPY/PROOF) |
| `server/` | FastAPI reference REST server exposing the protocol over HTTP |
| `policy-engine/` | (stub — see ROADMAP.md Phase 2: externalized policy DSL) |
| `client/` | (stub — see ROADMAP.md Phase 3: desktop/browser/mobile client SDK shells) |

## Quickstart

```bash
pip install -r requirements.txt --break-system-packages

# Run the full protocol end-to-end, in-process:
python3 ../tests/integration/demo_full_handshake.py

# Or run the unit test suite:
python3 -m pytest ../tests/unit -v

# Or start the REST server and drive it over HTTP:
cd server && uvicorn api:app --reload
```

## What's implemented (Phase 1)

- Full 9-message handshake (RFC-0001 §4), in-process and over HTTP
- Identity Vector compilation with domain-separated, salted, consented
  hashing of device/behavior/context signals (RFC-0001 §7, §10)
- Trust Score computation matching the formal model exactly (unit-tested
  against the worked example in `formal-model.md` §7)
- **SQLite-backed persistence** (`storage/sqlite_store.py`) — subject
  baselines and trust history survive process restarts, so running
  `identitydna login` repeatedly shows real trust progression:
  `DENY (41.42) → STEP_UP (55.02) → STEP_UP (70.02, plateau)` for the
  same demo device. Use `identitydna reset` to start over.
- Session DNA generation, rotation, and rejection of superseded
  generations (RFC-0001 §9)
- Ed25519 transcript-bound proofs and X25519 ephemeral ECDH for forward
  secrecy
- 28 passing unit/integration tests, including a regression test for the
  history-deadlock fix (see `CHANGELOG.md`)

## What's explicitly NOT implemented yet (see ROADMAP.md)

- Multi-language SDKs (Rust/Go/Java/JS/C#/C++) — Python only so far
- Persistent storage (everything is in-memory)
- TLS channel binding (see threat-model.md §3.2, flagged as a residual risk)
- Policy DSL / externalized configuration
- Fuzz/property/stress/performance test suites (only unit + one
  integration test exist)
- Desktop/browser/mobile client implementations
