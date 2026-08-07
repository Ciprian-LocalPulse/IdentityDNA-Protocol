# IdentityDNA Protocol SDK — TypeScript / JavaScript

Status: **Implemented (Phase 1)**. A reference client SDK for RFC-0001,
verified byte-for-byte interoperable with the Python reference
implementation (`reference/`) — not just "similar", but producing
**identical cryptographic digests** for identical input. See
[Interoperability](#interoperability) below.

## What's here

| Module | Mirrors (Python) | Purpose |
|---|---|---|
| `src/crypto/primitives.ts` | `reference/crypto/primitives.py` | BLAKE3 hashing, HKDF, canonical JSON, CSPRNG |
| `src/crypto/signatures.ts` | `reference/crypto/signatures.py` | Ed25519 signing/verification |
| `src/crypto/keyAgreement.ts` | `reference/crypto/keyagreement.py` | X25519 ephemeral ECDH |
| `src/entropy/normalizer.ts` | `reference/entropy-engine/normalizer.py` | Device/behavior/context normalization (RFC-0001 §10) |
| `src/identity/identityVector.ts` | `reference/identity-engine/identity_vector.py` | Identity Vector compilation (RFC-0001 §7) |
| `src/verifier/clientSession.ts` | `reference/verifier/verifier.py` | Client-side handshake message builder |
| `src/demo/demoHttpClient.ts` | `tests/integration/demo_http_client.py` | Full handshake demo over HTTP against the Python server |

## Install

```bash
cd sdk/javascript
npm install
npm run build
```

Requires Node.js 20+ (uses native `fetch`, `node:crypto`, ES2022 target).

## Run the test suite

```bash
npm test
```

17 tests (crypto primitives, Ed25519/X25519 round-trips, Identity Vector
properties, fail-closed handling of malformed input — the same defensive
checks added to the Python side after the DoS bug documented in
`../../CHANGELOG.md`).

## Run the cross-language demo

This is the actual point of a second-language SDK: proving a **different
runtime, different crypto library, different language** can complete a
real handshake against the Python reference server.

**Terminal 1** — start the Python server:
```bash
cd ../../reference/server
python -m uvicorn api:app --reload --port 8123
```

**Terminal 2** — run the TypeScript client:
```bash
npm run demo
```

You should see a full `HELLO → CHALLENGE → ENTROPY → IDENTITY_ACK →
PROOF → TRUST_RESULT` exchange, where the `PROOF`'s Ed25519 signature
was generated in TypeScript (`@noble/curves`) and verified server-side
in Python (`PyNaCl`). If the transcript hash construction or canonical
JSON serialization differed between the two implementations even
slightly, this would fail with `ERR_SIGNATURE_INVALID` — it doesn't,
which is the actual proof of interoperability, not just an assertion of it.

Run it 2-3 times to see the same `DENY → STEP_UP` trust-score
progression as the Python CLI demo (same SQLite persistence backend,
see `../../CHANGELOG.md`).

## Interoperability

`tests/interop/test_ts_python_parity.py` (in the repo root) runs both
implementations against identical inputs and asserts **byte-identical**
output for: domain-separated BLAKE3 hashes, HKDF, Device/Behavior/Context
normalization digests, and the full Identity Vector (`iv_digest` and the
first 5 vector components, `1e-10` precision).

This caught two real bugs during development, worth knowing about if
you're porting the SDK to a 3rd language:

1. **HKDF vs HKDF-Expand.** `hkdfExpandVector` (used to expand a digest
   into the 256-dim Identity Vector layer, formal-model.md §2.1) MUST
   use expand-only HKDF (`@noble/hashes/hkdf.js`'s `expand()`, matching
   Python's `cryptography.hazmat...HKDFExpand`) — NOT full
   extract-then-expand HKDF (`hkdf()`). Using full HKDF silently
   produces a *different but still valid-looking* Identity Vector,
   with no error, which would break cross-implementation trust
   comparisons in a very hard-to-notice way.
2. **Digest concatenation shape.** The `iv_digest` hash input must be
   ONE flat concatenated byte blob (matching Python's `b"".join(...)`),
   not an array of individually length-prefixed parts (which is how
   `hashBlake3`'s multi-part domain separation works everywhere else in
   this codebase). Passing the 256 vector-component byte chunks as
   separate parts instead of one pre-joined blob produces a different
   digest.

Run the interop check yourself:
```bash
cd ../..   # repo root
python3 -m pytest tests/interop -v
```

## Known gaps vs. the Python reference

- No Session DNA generation/rotation/validation port yet (session-engine)
  — the demo only exercises the client (verifier) half of the protocol;
  session management stays server-side, which is architecturally correct,
  but a full SDK would still want typed helpers for `VERIFY`/`RENEW`.
- No Trust Engine port — trust scoring is intentionally server-only
  (RFC-0001 doesn't require clients to compute it), so this is not a gap
  so much as a design choice, noted here for clarity.
- `canonicalJson`'s number formatting has not been exhaustively verified
  against Python's `json.dumps` for edge cases (very large floats,
  `-0`, etc.) — fine for the string/UUID/base64-heavy message envelopes
  IDP actually sends, flagged for anyone extending it to carry raw
  floats in a transcript-hashed field.
