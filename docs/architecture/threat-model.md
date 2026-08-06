# IdentityDNA Protocol — Threat Model

Scope: this document analyzes threats against the protocol as defined in
RFC-0001. It follows STRIDE per message/asset and maps each threat to a
concrete mitigation already required by the RFC (cross-referenced) — this
is intentional: a threat model with no corresponding normative mitigation
is a to-do, not a finished analysis, and is marked as such.

## 1. Assets

| Asset | Description |
|---|---|
| Session DNA (`SDNA_k`) | Bearer-equivalent session credential |
| Identity Vector (`IV`) | Derived identity representation |
| Device DNA hash | Consented device fingerprint hash |
| Trust Score | Access-decision input |
| Ed25519 signing key | Client's long-term or per-session identity key |
| Consent receipts | Legal/audit record of collection consent |

## 2. Trust Boundaries

```
[ Untrusted Client Device ] --TLS 1.3--> [ Server / Verifier ] --> [ Trust Policy Store ]
                                              |
                                              v
                                     [ Relying Party App ]
```

The client device is fully untrusted; all client-supplied values (including
`device_dna_hash`) are treated as claims, not facts, until corroborated by
history (§3.3 of the formal model) and cross-checked risk rules.

## 3. Threats and Mitigations

### 3.1 Replay

**Attack**: Attacker captures a valid `PROOF` or `VERIFY` message and
resends it later or to a different session.

**Mitigation**: `msg_id` uniqueness enforcement (RFC-0001 §4, `ERR_REPLAY`),
timestamp window (`ERR_CLOCK_SKEW`), and transcript-bound signatures
(§11.2) mean a captured `PROOF` cannot be replayed against a new
`CHALLENGE`/`server_nonce` pair — the signature covers the whole
transcript including the fresh server nonce.

**Residual risk**: Replay within the `±120s` window against the *same*
unexpired session is bounded by `msg_id` de-duplication; servers MUST
maintain a `msg_id` set per active session (not globally, for memory
bounds) with TTL ≥ clock skew window.

### 3.2 Phishing / Relay (Real-time MITM proxy)

**Attack**: Victim is tricked into completing the handshake through an
attacker-controlled relay that forwards messages to the real server in
real time, then hijacks the resulting `SESSION_DNA`.

**Mitigation**: Session DNA is bound to the ephemeral ECDH transcript
(§9 of RFC), which in turn should be bound to the TLS channel via
channel binding (`tls-exporter`, RFC 9266) — **implementations SHOULD
implement TLS channel binding**; this is flagged as a SHOULD, not yet a
MUST, pending a channel-binding profile in a future RFC revision. Until
then, real-time relay/AiTM attacks are a **known residual risk**, mitigated
only partially by Trust Engine context checks (impossible travel,
IP reputation) that may flag the relay's egress IP as anomalous.

### 3.3 Credential Stuffing

**Attack**: Automated attempts across many stolen username/password pairs.

**Mitigation**: IDP does not use static passwords as its primary factor;
Identity Vector + Trust Score means a correct-looking credential alone
(if any credential layer is composed alongside IDP) does not yield
`ALLOW` — `S_history` and `S_context` will be low for a first-seen device
context, producing `STEP_UP` or `DENY` (§3 of formal model). Rate limiting
(`ERR_RATE_LIMITED`) MUST also be applied at the gateway.

### 3.4 Session Hijacking

**Attack**: Attacker steals an active `SDNA_k` (e.g. via XSS, malware) and
uses it directly.

**Mitigation**: Mandatory rotation (`rotation_interval_s`, default 300s)
bounds the window of usability. Superseded `SDNA_k` values MUST be
rejected (RFC §9), so a stolen value not immediately used becomes
worthless at the next rotation. This does **not** protect against
real-time use of a freshly stolen `SDNA_k` — that is mitigated only by
continuous Trust Engine evaluation (behavioral drift, risk rules) at the
next `VERIFY`, not prevented outright. Relying Parties handling
high-value resources SHOULD shorten `rotation_interval_s`.

### 3.5 MITM (passive/active on the wire)

**Mitigation**: Delegated entirely to TLS 1.3+ (RFC-0001 §1, mandatory).
IDP provides no confidentiality of its own and explicitly assumes a
secure channel; running IDP over plaintext HTTP is non-conformant.

### 3.6 Device Theft

**Attack**: Attacker gains physical possession of an already-authenticated
device.

**Mitigation**: Out of scope for the wire protocol (this is an endpoint
security problem), but the continuous verification model (behavioral
sampling per `VERIFY`) is structurally more resistant than a
"login-once" model: a markedly different typing cadence/pointer entropy
after theft can lower `S_identity` and trigger `STEP_UP` mid-session.
This is a probabilistic mitigation, not a guarantee, and MUST be
documented as such to Relying Parties (no overselling behavioral
biometrics).

### 3.7 Insider Threat (server operator)

**Attack**: A malicious or compromised server operator accesses stored
Identity Vectors / Device DNA to de-anonymize or track users.

**Mitigation**: RFC-0001 §10 mandates hashing of raw device signals
before transmission and zero-retention of raw inputs by default. This
limits, but does not eliminate, insider risk — the server still holds
`IV` and `device_dna_hash`, which are pseudonymous but potentially
linkable across sessions for the *same* Relying Party. Cross-Relying-Party
linkage MUST NOT occur (§10.4); implementations SHOULD use per-RP salts
in `normalize_device` to prevent a compromised operator from correlating
the same device across unrelated Relying Parties.

### 3.8 Supply Chain

**Attack**: Compromise of an SDK dependency (e.g. a malicious npm/PyPI
package) to exfiltrate signing keys or tamper with Trust Score
computation client-side.

**Mitigation**: Out of band of the wire protocol. Organizational
mitigations: reproducible builds, dependency pinning + hash verification,
signed releases (see `SECURITY.md`), and minimizing the dependency
surface of the reference crypto module (this repo intentionally wraps
only well-audited libraries — `cryptography`, `PyNaCl` — rather than
reimplementing primitives, per RFC-0001 §11.1).

## 4. Explicitly Out of Scope

- Physical/endpoint compromise below the OS trust boundary.
- Quantum-adversary resistance (Ed25519/X25519 are not post-quantum;
  a PQ-hybrid suite is tracked in `ROADMAP.md` as future work).
- Social engineering of the Relying Party's support staff.

## 5. Summary Table

| Threat | STRIDE Category | Status |
|---|---|---|
| Replay | Tampering / Spoofing | Mitigated (normative) |
| Phishing/Real-time relay | Spoofing | Partially mitigated — residual risk documented |
| Credential Stuffing | Spoofing | Mitigated via Trust Engine + rate limiting |
| Session Hijacking | Spoofing / Elevation | Bounded, not eliminated |
| MITM (wire) | Tampering / Info Disclosure | Delegated to TLS (mandatory) |
| Device Theft | Spoofing | Probabilistic mitigation only |
| Insider Threat | Info Disclosure | Reduced via hashing + zero raw retention |
| Supply Chain | Tampering | Organizational controls, out of wire protocol |
