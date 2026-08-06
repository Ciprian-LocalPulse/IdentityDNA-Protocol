```
RFC-0001
IdentityDNA Protocol (IDP)
Version 1.0.0-draft
Normative Specification
Status: Draft Standard
```

## 0. Conformance Language

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be
interpreted as described in RFC 2119 / RFC 8174.

An implementation is **conformant** if and only if it satisfies every MUST/MUST NOT
requirement in this document. SHOULD/SHOULD NOT items are recommended but not
required for conformance; deviations MUST be documented by the implementer.

---

## 1. Scope

IdentityDNA Protocol (IDP) defines a session-oriented, continuously-verified
identity and trust framework. It is not a credential format and it is not a
transport protocol; it runs over an authenticated transport (TLS 1.3 or later
MUST be used for all wire traffic — IDP provides no confidentiality of its own).

IDP defines:

1. The **message set** exchanged between Client and Server.
2. The **state machine** governing a Session DNA's lifecycle.
3. The **error code registry**.
4. The **rules** for computing Trust Score, Identity Vector, and Session DNA.

IDP does **not** define: transport security (delegated to TLS), storage formats,
or UI/UX. IDP MUST NOT be used as a replacement for transport encryption.

---

## 2. Terminology

| Term | Definition |
|---|---|
| **Identity Vector (IV)** | A fixed-length numeric vector derived deterministically from multi-layer entropy (device, behavioral, contextual). See §7. |
| **Identity Stream** | The time-ordered sequence of Identity Vectors produced during a session. |
| **Trust Score (TS)** | A scalar in `[0, 100]` produced by the Trust Engine from the Identity Stream and contextual signals. See §8. |
| **Session DNA (SDNA)** | An ephemeral, cryptographically-bound session identifier generated once per session and rotated per §9. |
| **Device DNA** | A consented, disclosed, hashed fingerprint of client-environment signals. See §10 and the Privacy Addendum. |
| **Verifier** | The party (typically the Server) that validates proofs without learning the underlying secret material. |
| **Relying Party (RP)** | The application/service that consumes IDP's trust decision. |

---

## 3. Protocol Overview

IDP defines nine message types exchanged in a fixed order (the **Handshake**),
followed by a **Verification Loop** that runs for the duration of the session.

```
Client                                   Server
  |-------------- HELLO ------------------>|
  |<------------- CHALLENGE ----------------|
  |-------------- ENTROPY ----------------->|
  |<------------- IDENTITY_ACK -------------|
  |-------------- PROOF ------------------->|
  |<------------- TRUST_RESULT -------------|
  |<------------- SESSION_DNA --------------|
  |==== periodic ====> VERIFY <====================>|
  |-------------- RENEW / REVOKE ----------->|
```

---

## 4. Message Set (Normative)

Every IDP message is a JSON object (CBOR is an approved alternative encoding,
§4.9) with a mandatory envelope:

```json
{
  "idp": "1.0",
  "type": "<MESSAGE_TYPE>",
  "msg_id": "<uuid-v4>",
  "ts": "<RFC-3339 UTC timestamp>",
  "body": { }
}
```

Field rules:
- `idp` MUST equal the protocol version. Servers MUST reject unknown major
  versions with `ERR_VERSION_UNSUPPORTED`.
- `msg_id` MUST be a fresh UUIDv4 per message. Servers MUST reject a `msg_id`
  seen before for the same session with `ERR_REPLAY`.
- `ts` MUST be within `±120s` of server time (clock skew tolerance) or the
  server MUST reject with `ERR_CLOCK_SKEW`.

### 4.1 `HELLO` (Client → Server)

Initiates a session.

```json
{
  "type": "HELLO",
  "body": {
    "client_version": "1.0.0",
    "supported_suites": ["ed25519-blake3-argon2id", "x25519-sha3-hkdf"],
    "nonce_c": "<32-byte base64url>"
  }
}
```

### 4.2 `CHALLENGE` (Server → Client)

```json
{
  "type": "CHALLENGE",
  "body": {
    "selected_suite": "ed25519-blake3-argon2id",
    "server_nonce": "<32-byte base64url>",
    "challenge": "<32-byte base64url random>",
    "difficulty": 0
  }
}
```

`difficulty` is an optional proof-of-work exponent (§11.4) the server MAY set
`> 0` under load or suspected abuse to add asymmetric cost to `HELLO` flooding.

### 4.3 `ENTROPY` (Client → Server)

Carries the raw multi-layer entropy inputs used to derive the Identity Vector.
Raw device signals MUST NOT be transmitted in the clear; only normalized,
hashed representations per §10 are permitted.

```json
{
  "type": "ENTROPY",
  "body": {
    "device_dna_hash": "<hex>",
    "behavioral_sample": { "typing_cadence_ms": [...], "pointer_entropy": 0.0 },
    "context": { "tz_offset_min": 120, "locale": "ro-RO" },
    "consent_receipt_id": "<uuid>"
  }
}
```

`consent_receipt_id` MUST reference a valid, unexpired consent record
(§10.2). Servers MUST reject `ENTROPY` lacking a valid consent receipt with
`ERR_CONSENT_MISSING`.

### 4.4 `IDENTITY_ACK` (Server → Client)

```json
{
  "type": "IDENTITY_ACK",
  "body": { "identity_vector_id": "<uuid>", "iv_digest": "<hex, 32 bytes>" }
}
```

### 4.5 `PROOF` (Client → Server)

```json
{
  "type": "PROOF",
  "body": {
    "signature": "<base64, Ed25519 over transcript hash>",
    "public_key": "<base64, 32 bytes>"
  }
}
```

The transcript hash is defined in §11.2. The Client MUST sign the transcript,
not raw fields, to bind the proof to the entire handshake so far.

### 4.6 `TRUST_RESULT` (Server → Client)

```json
{
  "type": "TRUST_RESULT",
  "body": { "trust_score": 92.4, "decision": "ALLOW", "risk_flags": [] }
}
```

`decision` MUST be one of `ALLOW`, `STEP_UP`, `DENY` (§8.4).

### 4.7 `SESSION_DNA` (Server → Client)

```json
{
  "type": "SESSION_DNA",
  "body": {
    "session_id": "<uuid>",
    "sdna": "<base64, 32 bytes>",
    "issued_at": "<RFC-3339>",
    "expires_at": "<RFC-3339>",
    "rotation_interval_s": 300
  }
}
```

### 4.8 `VERIFY` (bidirectional, periodic)

```json
{ "type": "VERIFY", "body": { "session_id": "<uuid>", "sdna_proof": "<base64>" } }
```

Sent by the Client at most once per `rotation_interval_s`. The Server responds
with a new `SESSION_DNA` (rotation) or `ERR_SESSION_EXPIRED` / `ERR_SESSION_REVOKED`.

### 4.9 `REVOKE` (bidirectional)

```json
{ "type": "REVOKE", "body": { "session_id": "<uuid>", "reason": "<string>" } }
```

Either party MAY revoke at any time. Servers MUST treat a received `REVOKE`
as immediately terminal for that `session_id`.

### 4.10 Encoding

JSON (UTF-8) is the default wire encoding. CBOR (RFC 8949) MAY be used when
negotiated in `HELLO.supported_suites` via an `+cbor` suffix. Both encodings
MUST produce byte-identical transcript hashes when canonicalized per §11.2.

---

## 5. State Machine (Normative)

```
        HELLO
          |
          v
      [CHALLENGED] --timeout(30s)--> [EXPIRED]
          |
       ENTROPY
          v
      [ENTROPY_RECEIVED] --invalid consent--> [REJECTED]
          |
     IDENTITY_ACK
          v
      [AWAITING_PROOF] --timeout(30s)--> [EXPIRED]
          |
        PROOF
          v
      [VERIFYING] --sig invalid--> [REJECTED]
          |
    trust computed
          v
      [TRUST_EVALUATED] --DENY--> [DENIED]
          |  (ALLOW | STEP_UP)
          v
      [ACTIVE] <---VERIFY (rotate)---> [ACTIVE]
          |
     REVOKE | expires_at reached
          v
      [TERMINATED]
```

Implementations MUST reject any message type not valid for the current state
with `ERR_STATE_INVALID`, including well-formed messages arriving out of order.

---

## 6. Error Code Registry (Normative)

| Code | Meaning | Retryable |
|---|---|---|
| `ERR_VERSION_UNSUPPORTED` | Unknown/unsupported `idp` major version | No |
| `ERR_REPLAY` | `msg_id` reused within session | No |
| `ERR_CLOCK_SKEW` | `ts` outside tolerance | Yes (after resync) |
| `ERR_STATE_INVALID` | Message not valid in current state | No |
| `ERR_CONSENT_MISSING` | No valid consent receipt for entropy collection | No |
| `ERR_SUITE_UNSUPPORTED` | No overlap in `supported_suites` | No |
| `ERR_SIGNATURE_INVALID` | Proof signature verification failed | No |
| `ERR_TRUST_INSUFFICIENT` | Trust score below policy threshold | Conditionally (STEP_UP) |
| `ERR_SESSION_EXPIRED` | `expires_at` passed | Client MUST re-handshake |
| `ERR_SESSION_REVOKED` | Session was explicitly revoked | No |
| `ERR_RATE_LIMITED` | Too many attempts from origin | Yes (backoff) |
| `ERR_MALFORMED` | Envelope/body fails schema validation | No |

New codes MUST be registered here before being emitted by a conformant
implementation. Implementations MUST NOT invent undocumented codes.

---

## 7. Identity Vector — Normative Rule

The Identity Vector **MUST** be computed as:

```
IV = Normalize( f_device(D) ⊕ f_behavior(B) ⊕ f_context(C) )
```

where `f_device`, `f_behavior`, `f_context` are documented, versioned
normalization functions (see `docs/mathematics/formal-model.md` §2), `⊕` is
a domain-separated concatenation-then-hash combinator (never raw XOR of
unequal-length attacker-influenced fields), and `Normalize` maps the digest
onto the unit hypersphere in `R^n` (default `n = 256`).

Servers MUST discard raw `D`, `B`, `C` inputs after computing `IV` unless the
Relying Party has a documented, consented retention policy (§10.2). Default
retention of raw signals is **zero**.

## 8. Trust Score — Normative Rule

See `docs/mathematics/formal-model.md` §3 for the full formal definition. In
summary:

```
TS = clamp( w1*S_identity + w2*S_history + w3*S_context - w4*R_risk, 0, 100 )
```

`decision` MUST be derived from policy-configured thresholds:
- `TS >= allow_threshold` → `ALLOW`
- `step_up_threshold <= TS < allow_threshold` → `STEP_UP`
- `TS < step_up_threshold` → `DENY`

Default thresholds: `allow_threshold = 80`, `step_up_threshold = 50`.
Relying Parties MUST be able to override thresholds per resource sensitivity.

## 9. Session DNA — Normative Rule

```
SDNA_0 = HKDF( ikm = ECDH(client_eph, server_eph), salt = transcript_hash,
               info = "IDP-SESSION-DNA-v1", L = 32 )
SDNA_(k+1) = HKDF( ikm = SDNA_k, salt = rotation_nonce_k, info = "IDP-ROTATE-v1", L = 32 )
```

Session DNA MUST rotate at least every `rotation_interval_s` (default 300s).
A `SDNA_k` value MUST NOT be valid after `SDNA_(k+1)` has been issued
(no session DNA reuse window). Servers MUST bind `SDNA_k` to `session_id`
and MUST reject a `VERIFY` presenting a superseded `SDNA_k`.

## 10. Device DNA — Privacy Addendum (Normative)

This section is normative and takes precedence over any implementation note
elsewhere in this repository.

1. Device DNA collection **MUST** be disclosed to the end user in
   plain language before collection.
2. Collection **MUST** be gated on an explicit, revocable, timestamped
   consent record (`consent_receipt_id`, §4.3). Absence of a valid receipt
   MUST result in `ERR_CONSENT_MISSING`.
3. Only a **hash** of normalized signals may leave the client
   (`device_dna_hash`); raw values (exact GPU string, exact screen size,
   full font list, etc.) MUST NOT be transmitted or logged server-side.
4. Implementations MUST NOT use Device DNA for cross-site tracking or for
   any purpose beyond the trust decision for the consenting Relying Party.
5. Implementations MUST provide a documented mechanism for a user to
   request deletion of any retained Device DNA derivative.
6. High-entropy passive fingerprinting techniques designed to defeat
   privacy-mode browsers or evade user awareness are explicitly **out of
   scope and non-conformant**. IDP is not a covert-tracking protocol.

## 11. Cryptographic Requirements

### 11.1 Approved Primitives

| Purpose | Primitive | Notes |
|---|---|---|
| Hashing | BLAKE3-256 (preferred) or SHA3-256 | Domain-separated per use (§11.3) |
| Signatures | Ed25519 | RFC 8032 |
| Key Agreement | X25519 | RFC 7748 |
| KDF | HKDF-SHA256 (RFC 5869) | For SDNA and key expansion |
| Password/low-entropy KDF | Argon2id | For any human-secret-derived material only |
| AEAD | ChaCha20-Poly1305 (preferred) or AES-256-GCM | For any encrypted-at-rest artifacts |
| RNG | CSPRNG only (`os.urandom` / platform CSPRNG) | MUST NOT use non-cryptographic RNG anywhere in the protocol path |

No implementation may substitute a non-approved primitive without a
successor RFC. Implementations MUST NOT design novel cryptographic
primitives; originality is confined to protocol composition, not primitives.

### 11.2 Transcript Hash

```
transcript_hash = BLAKE3( "IDP-TRANSCRIPT-v1" || HELLO_bytes || CHALLENGE_bytes
                            || ENTROPY_bytes || IDENTITY_ACK_bytes )
```

Canonical byte serialization MUST use RFC 8785 (JCS) for JSON.

### 11.3 Domain Separation

All hash invocations MUST include a fixed ASCII domain-separation prefix
unique to the invocation site (e.g. `"IDP-SESSION-DNA-v1"`,
`"IDP-DEVICE-DNA-v1"`, `"IDP-TRANSCRIPT-v1"`). Reusing one hash output
across two different security purposes without distinct domain separation
is non-conformant.

### 11.4 Proof of Work (Optional)

Under `difficulty > 0`, Clients MUST find `nonce` such that
`leading_zero_bits( BLAKE3(challenge || nonce) ) >= difficulty` before
sending `ENTROPY`. This is an anti-flood measure only and MUST NOT be
relied upon as a security boundary.

---

## 12. Versioning

IDP follows semantic versioning at the protocol level (`MAJOR.MINOR.PATCH`).
Breaking wire-format changes require a MAJOR bump and a new RFC. This
document defines `1.0.0-draft`; it becomes `1.0.0` upon ratification by the
process in `CONTRIBUTING.md`.

---

## 13. Security Considerations

See `docs/architecture/threat-model.md` for the full threat model. Summary
obligations imposed by this RFC: transport confidentiality is delegated to
TLS 1.3+; the protocol supplies replay resistance (§4, `msg_id` + `ts`),
transcript-binding of proofs (§11.2), forward secrecy of Session DNA via
ephemeral ECDH (§9), and privacy-by-design Device DNA collection (§10).

## 14. IANA / Registry Considerations

Not applicable in this draft; a future revision may register a media type
`application/idp+json`.
