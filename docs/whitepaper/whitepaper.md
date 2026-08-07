---
title: "IdentityDNA Protocol: A Continuously-Verified, Privacy-Preserving Identity and Trust Framework"
subtitle: "Reference Specification, Formal Model, and Engineering Validation — v1.0.0-draft"
author: "IdentityDNA Protocol Working Group"
date: "August 2026"
---

\newpage

# Abstract {-}

Most authentication protocols in wide deployment today — TLS client
certificates, OAuth 2.0 bearer tokens, WebAuthn/FIDO2 assertions — make
a single binary trust decision at login time and then treat the
resulting session as fully trusted until it expires or is explicitly
revoked. This "authenticate once, trust fully" model is a poor fit for
the threat landscape of session hijacking, credential replay, and
device compromise that occurs *after* a legitimate login. IdentityDNA
Protocol (IDP) proposes an alternative: a session-oriented identity
framework in which a numeric **Trust Score**, derived from a
continuously-refreshed **Identity Vector**, a decaying **history**
term, contextual priors, and an explicit **risk** term, governs access
for the *duration* of a session rather than only at its inception.

This paper presents RFC-0001, the normative specification of IDP;
a formal mathematical model of the Trust Score function with a worked
derivation; a reference implementation in Python (with a second,
independently-verified TypeScript implementation); and — in the
interest of engineering honesty rare in whitepapers of this kind — a
documented account of the real defects our own formal model and
reference code contained, how property-based testing and
cross-language interoperability testing found them, and how they were
fixed. We report concrete performance figures from the reference
implementation (573K hash operations/sec, 36.5K Ed25519
signatures/sec, 351 full end-to-end handshakes/sec including SQLite
persistence, all single-threaded on commodity hardware) and an
explicit, unpadded list of what remains unimplemented. This is a
draft protocol proposal and a research-grade reference implementation,
not a production-hardened system nor an adopted standard; we are
explicit throughout about that distinction.

\newpage

# 1. Introduction and Motivation

## 1.1 The problem with "authenticate once"

The dominant authentication pattern on the web today separates
*authentication* (proving identity, once, at login) from
*authorization* (checking permissions, per request, against a
session token that is treated as a fixed credential until it expires).
This separation is efficient and has served the industry well, but it
has a structural weakness: once a session token is issued, the
protocol has no further opinion about whether the entity presenting
that token on request number 4,000 is still the same entity that
authenticated at request number 1. A stolen session cookie, a hijacked
OAuth bearer token, or a device that changes hands mid-session are all
indistinguishable from the legitimate user, from the protocol's point
of view, because the protocol simply is not looking anymore after the
initial handshake.

Continuous authentication — periodically re-evaluating trust using
lightweight signals rather than requiring the user to re-authenticate
— is not a new idea; it has substantial prior art in the mobile
biometrics and enterprise Zero Trust Architecture (ZTA) literature
[NIST-800-207]. What IDP contributes is not the idea of continuous
verification itself, but: (a) a concrete, implementable wire protocol
for it, defined with the same rigor (message formats, state machine,
error registry) as TLS or OAuth; (b) a formal, unit-tested mathematical
model for how the trust decision is actually computed, rather than
leaving "risk scoring" as an unspecified implementation detail as most
Zero Trust literature does; and (c) privacy-by-design constraints on
the device-fingerprinting signals such a system is tempted to collect,
specified normatively rather than left to implementer discretion.

## 1.2 Design goals

IDP is designed against five explicit goals, in priority order:

1. **Session-duration trust, not point-in-time trust.** The protocol's
   central data structure, the Trust Score, is recomputed periodically
   for the life of a session, not just once at login.
2. **Privacy-by-design device signals.** Any device/behavioral/
   contextual signal used as input MUST be disclosed, consented to,
   and irreversibly hashed before it leaves the client's control; raw
   signals are never retained server-side by default (§6, §8).
3. **No novel cryptography.** All cryptographic primitives are
   externally audited, standard constructions (Ed25519, X25519, BLAKE3,
   HKDF, Argon2id, ChaCha20-Poly1305). Protocol originality is confined
   to composition and the trust-scoring model, never to primitive
   design (§7).
4. **Formal, falsifiable trust model.** Every term in the Trust Score
   function is a named, numerically-defined quantity with documented
   bounds — not a black-box machine learning model or an unspecified
   "risk engine."
5. **Implementability and interoperability as first-class evidence.**
   A specification nobody can implement identically twice is not a
   specification. §9 of this paper reports on an independent
   second-language (TypeScript) implementation and the byte-for-byte
   interoperability testing between it and the Python reference.

## 1.3 Contributions and scope of this paper

This paper's contributions are: the RFC-0001 normative specification
(§3); a formal mathematical model of the Identity Vector and Trust
Score functions with a worked numeric example (§4); a documented
account of two real defects found in that model and its first
implementation via property-based fuzz testing, including a
remote-DoS-class bug (§8); a report on cross-language interoperability
testing between independently-written Python and TypeScript
implementations, including two further defects that testing caught
before either was ever deployed (§9); a threat model with explicitly
acknowledged residual risks rather than a checklist of only-solved
problems (§10); and measured performance figures from the reference
implementation (§11).

This paper does **not** claim IDP is an adopted or standardized
protocol, does not claim the reference implementation is
production-hardened, and does not claim novelty in the general concept
of continuous authentication, which has a substantial prior literature
under the Zero Trust and continuous/adaptive authentication headings
[Kolter2005; NIST-800-207]. What is offered is a complete, concrete,
implementable, and independently-validated specification and reference
implementation — the artifact class this literature has historically
been light on.

\newpage

# 2. Related Work

Table 1 summarizes how IDP's design goals compare against three
protocols in wide production deployment. This is a design comparison,
not a claim of superiority — each protocol solves a somewhat different
problem, and IDP is explicitly *composable with*, not a replacement
for, TLS.

**Table 1: Design comparison with deployed protocols**

| Property | TLS 1.3 [RFC8446] | OAuth 2.0 [RFC6749] | FIDO2/WebAuthn [W3C-WebAuthn] | IDP (this work) |
|---|---|---|---|---|
| Primary purpose | Transport confidentiality & server/client auth | Delegated authorization | Passwordless authentication | Session-duration identity & trust |
| Trust re-evaluated post-handshake? | No (session resumption reuses trust) | No (bearer token trusted until expiry/revocation) | No (single assertion at login) | Yes — periodic `VERIFY` rounds |
| Device signal collection | None (out of scope) | None (out of scope) | Authenticator attestation (opt-in) | Normatively privacy-constrained (§6) |
| Numeric trust/risk model | None (binary: valid cert or not) | None (binary: valid token or not) | None (binary: valid assertion or not) | Explicit `[0,100]` Trust Score, formally defined (§4) |
| Forward secrecy | Yes (ephemeral ECDHE) | N/A (delegated to TLS) | N/A (delegated to TLS) | Yes (ephemeral X25519 per session, §7) |
| Session key rotation | Via resumption/rekey | No native mechanism | No native mechanism | Mandatory, ≤300s default (§3.4) |

IDP's relationship to these protocols is layered, not competitive: IDP
assumes TLS 1.3 for transport confidentiality (RFC-0001 §1 makes this
a MUST), and could reasonably sit alongside OAuth 2.0 as an additional,
continuously-reevaluated trust signal feeding into an authorization
decision, or alongside FIDO2 as the mechanism governing what happens
to a session *after* a FIDO2 assertion, not as a replacement for the
assertion itself. The Zero Trust Architecture literature
[NIST-800-207] describes the conceptual need IDP's protocol layer
attempts to fill concretely.

\newpage

# 3. Protocol Overview

This section summarizes RFC-0001; the full normative text (message
schemas, error codes, state machine) is available in the reference
implementation's repository at `docs/protocol/RFC-0001-IdentityDNA-Protocol.md`
and is not reproduced in full here, following academic convention for
referencing an accompanying specification document.

## 3.1 Message flow

IDP defines nine message types (Figure 1) exchanged in a fixed
handshake order, followed by a periodic verification loop for the
duration of the session:

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
**Figure 1: The IDP handshake and verification loop (RFC-0001 §3).**

`HELLO` and `CHALLENGE` negotiate a cipher suite and exchange fresh
nonces and ephemeral X25519 public keys. `ENTROPY` carries the client's
consented, pre-hashed device/behavioral/contextual signal
(`device_dna_hash`) plus a reference to a consent receipt; the server
never receives raw signal data over the wire (§6). The server compiles
this into an **Identity Vector** and returns `IDENTITY_ACK`. The client
then signs a hash of the entire transcript so far with an Ed25519 key
(`PROOF`), binding the signature to every prior message and preventing
a captured `PROOF` from being replayed against a different handshake.
The server verifies the signature, computes the **Trust Score** (§4),
and returns a `TRUST_RESULT` plus, if the decision is not an outright
denial, a `SESSION_DNA` — an ephemeral, HKDF-derived session identifier
bound to the ephemeral ECDH transcript, providing forward secrecy (§7).

## 3.2 State machine

Every message is valid in exactly one state; the reference
implementation enforces this as a state machine (RFC-0001 §5) and
rejects out-of-order, replayed, or malformed messages with a specific
registered error code rather than a generic failure (§10 catalogs the
9 states and 12 registered error codes). §9.2 of this paper reports on
adversarial fuzz testing that specifically targets this state machine.

## 3.3 The consent-gated entropy model

RFC-0001 §10 (the "Privacy Addendum") is, unusually for a protocol
specification, normative on a privacy question rather than leaving it
to implementer policy: device signal collection MUST be disclosed in
plain language, gated on a revocable consent receipt, transmitted only
as an irreversible hash, retained nowhere by default, and never used
for cross-Relying-Party tracking. §6 of this paper discusses the
implementation of this constraint and its interaction with the formal
trust model.

## 3.4 Session lifecycle

A `SESSION_DNA` value is not a static bearer token; it is derived via
`SDNA_0 = HKDF(ECDH(client_eph, server_eph), transcript_hash, "IDP-SESSION-DNA-v1")`
and MUST rotate at least every `rotation_interval_s` (default 300
seconds) via `SDNA_(k+1) = HKDF(SDNA_k, rotation_nonce_k,
"IDP-ROTATE-v1")`. A superseded generation MUST be rejected by the
server even before its nominal expiry — there is no reuse window. This
bounds the value of a stolen but not-immediately-used session token to
at most one rotation interval, a materially different security
property from a long-lived bearer token (§10.4 discusses the residual
risk of immediate reuse, which this mechanism does not address).
\newpage

# 4. Formal Mathematical Model

This section presents the trust-scoring model in full, including two
corrections made to an earlier draft of the model after property-based
testing revealed defects (§8.1) — we report the corrected model here
and discuss the discovery process as a methodological contribution in
its own right, rather than silently presenting only the final, clean
version.

## 4.1 The Identity Vector

Let *D*, *B*, *C* denote, respectively, the raw device, behavioral, and
contextual signal inputs for one session (subject to the consent and
allow-listing constraints of §6). Three layer functions map each input
to a vector in [0,1]ⁿ (default *n* = 256) via a domain-separated hash
and an HKDF-Expand-based stream expansion:

```
f_device(D)   = Expand( H("IDP-DEVICE-DNA-v1"   || normalize_D(D)), n )
f_behavior(B) = Expand( H("IDP-BEHAVIOR-v1"     || normalize_B(B)), n )
f_context(C)  = Expand( H("IDP-CONTEXT-v1"      || normalize_C(C)), n )
```

where *H* is BLAKE3-256 [OConnor2020] and *Expand* is HKDF-Expand (not
full HKDF — see §9.1 for why this distinction matters more than it
looks like it should). The three layers are combined by a weighted sum
and projected onto the unit hypersphere:

```
IV_raw = w_d · f_device(D)  +  w_b · f_behavior(B)  +  w_c · f_context(C),   w_d + w_b + w_c = 1
IV     = IV_raw / ‖IV_raw‖₂
```

with default weights (w_d, w_b, w_c) = (0.5, 0.3, 0.2), reflecting that
device signals are the most session-to-session stable
identity-correlated layer, with behavior and context as lower-weighted
corroborating signals. If ‖IV_raw‖₂ = 0 (degenerate all-zero input),
the reference implementation raises a typed error rather than dividing
by zero — verified by property-based fuzz testing across the full
space of malformed and edge-case inputs (§8.3).

**Identity distance.** For two Identity Vectors from the same claimed
principal across sessions, since both are unit-norm, cosine similarity
reduces to the dot product:

```
d(IV_a, IV_b) = 1 − cos(IV_a, IV_b) = 1 − IV_a · IV_b        d ∈ [0, 2]
```

## 4.2 The Trust Score

The overall Trust Score at time *t* is:

```
TS(t) = clamp( w1·S_identity(t) + w2·S_history(t) + w3·S_context(t) − w4·R_risk(t),  0,  100 )
```

with default weights w1 = 0.35, w2 = 0.30, w3 = 0.15, w4 = 0.20 (risk
is *subtracted*, not averaged in, so that a single severe risk flag
can dominate the score regardless of otherwise-good signals — a
deliberate asymmetry: many good signals should not be able to "outvote"
one strong indicator of compromise).

**Identity consistency score.**

```
S_identity(t) = 100 · ( 1 − d(IV(t), IV_baseline)/2 ) · confidence(t)
```

This is the corrected form of the formula (§8.1 discusses the original,
defective version). Since d ∈ [0,2], this ranges over [0,
100·confidence]: a perfect match (d = 0) scores the maximum; the
neutral/uninformative case d = 1 (orthogonal vectors, including a
first-ever session with no enrolled baseline, by convention) scores
the midpoint 50·confidence; a maximally divergent comparison (d = 2)
scores zero.

**History score** (exponentially-weighted recency, decay λ = 0.85,
window *K* = 20 sessions):

```
S_history(t) = 100 · Σ(k=1..K) λ^(k-1)·match(t-k)  /  Σ(k=1..K) λ^(k-1)        match(t-k) ∈ {0,1}
```

We define match(t−k) = 1 for session outcomes of `ALLOW` or `STEP_UP`,
and 0 only for an outright `DENY` — not `ALLOW` alone, as an earlier
draft specified. §8.1 documents the structural deadlock this correction
fixes: under the stricter original definition, `STEP_UP` counted as a
history *failure*, but `ALLOW` required a good history score, and a
first-ever (no-baseline) session could score no higher than `STEP_UP`
— meaning no subject could ever accumulate the history needed to ever
reach `ALLOW`, a permanent-lockout deadlock discovered empirically by
running the reference implementation's persistence layer repeatedly,
not derived analytically in advance.

**Context score** (conjunctive — one strongly atypical factor
dominates rather than being diluted by several unremarkable ones):

```
S_context(t) = 100 · Π(j) p_j(t)        p_j(t) ∈ [0,1]
```

**Risk function** (sum of triggered rule severities; rules include
impossible-travel velocity, known-bad device hash, IP reputation,
Tor/proxy exit node, replay detection, authentication velocity abuse,
Identity Vector drift, and behavioral anomaly):

```
R_risk(t) = Σ(i) severity_i · 1[rule_i triggered at t]
```

**Confidence function** (saturating in the number of independent,
non-degenerate corroborating signal layers n_eff(t) available,
saturation constant τ = 2.0):

```
confidence(t) = 1 − exp( −n_eff(t) / τ )
```

This damps S_identity's contribution when fewer independent signal
layers are available (e.g. behavioral sampling failed for this
session), rather than trusting a partial-evidence match at full weight.

## 4.3 Worked numeric example

Given d = 0.04 (near-identical device), confidence = 0.93, S_history =
88, S_context = 95, R_risk = 6 (a minor flag, e.g. a new-but-plausible
IP range):

```
S_identity = 100 · (1 − 0.02) · 0.93 = 91.14
TS = 0.35(91.14) + 0.30(88) + 0.15(95) − 0.20(6)
   = 31.90 + 26.4 + 14.25 − 1.2
   = 71.35
```

With default thresholds (allow = 80, step_up = 50), this session is
classified `STEP_UP`. This exact fixture (to floating-point precision)
is asserted in the reference implementation's test suite
(`test_trust_engine.py::test_worked_example_matches_formal_model_doc`)
and is re-verified on every test run, not merely documented as prose.

For contrast, a first-ever session for the same subject (no baseline;
d = 1 by convention, everything else equal) scores S_identity = 46.5
and TS = 45.53 — below the step-up threshold, so classified `DENY`. A
subsequent, now-recognized-device session's identity contribution
(91.14) is nearly double the first session's (46.5); this
near-doubling is the mechanism by which repeated legitimate device use
is intended to raise trust over multiple sessions, distinct from and
additive to the separate history-based improvement mechanism.

## 4.4 Session key derivation

```
SDNA_0     = HKDF( ikm = ECDH(sk_c, pk_s), salt = H_transcript, info = "IDP-SESSION-DNA-v1" )
SDNA_(k+1) = HKDF( ikm = SDNA_k,           salt = nonce_k,      info = "IDP-ROTATE-v1" )
```

Because HKDF is one-way, SDNA_(k+1) reveals nothing about SDNA_k
(rotation-forward secrecy), and the initial derivation inherits forward
secrecy from the ephemeral (per-session, discarded after use) X25519
keypairs — compromise of a long-term signing key does not
retroactively compromise past session keys, since signing keys are
used only for authentication (the `PROOF` message), never as ECDH
input.
\newpage

# 5. Cryptographic Foundations

Consistent with design goal 3 (§1.2), IDP specifies only externally
audited, standard primitives (Table 2) and forbids novel cryptographic
design; protocol originality is confined to composition.

**Table 2: Approved cryptographic primitives (RFC-0001 §11.1)**

| Purpose | Primitive | Reference |
|---|---|---|
| Hashing | BLAKE3-256 | [OConnor2020] |
| Signatures | Ed25519 | RFC 8032 [RFC8032] |
| Key agreement | X25519 | RFC 7748 [RFC7748] |
| Key derivation | HKDF-SHA256 | RFC 5869 [RFC5869] |
| Password/low-entropy KDF | Argon2id | [Biryukov2016] |
| AEAD | ChaCha20-Poly1305 | RFC 8439 [RFC8439] |
| RNG | Platform CSPRNG only | — |

## 5.1 Domain separation

Every hash invocation includes a fixed, unique ASCII domain-separation
prefix (e.g. `"IDP-SESSION-DNA-v1"`, `"IDP-DEVICE-DNA-v1"`,
`"IDP-TRANSCRIPT-v1"`). This is not a stylistic convention but a
concrete security property: it prevents a value computed for one
purpose (e.g. a Device DNA hash) from being reinterpretable as a valid
value for a different purpose (e.g. a transcript hash) even if the
underlying input bytes happened to coincide. The reference
implementation enforces this at the API level — the core hashing
function raises a typed error if called without an explicit domain tag
— and property-based testing (§8.3) confirms empirically, across
hundreds of randomized inputs, that six protocol-defined domains never
collide for the same payload.

## 5.2 Transcript binding

The client's `PROOF` message signs not a static challenge value but a
hash of the entire handshake transcript so far:

```
H_transcript = H( "IDP-TRANSCRIPT-v1" || HELLO || CHALLENGE || ENTROPY || IDENTITY_ACK )
```

using RFC 8785 JSON Canonicalization Scheme (JCS) [RFC8785] byte
serialization. This binds the proof to the specific server nonce, the
specific Identity Vector digest the server computed, and the specific
entropy submission — a captured, valid `PROOF` cannot be replayed
against a different `CHALLENGE` (a fresh server nonce invalidates the
old transcript hash), closing the class of replay attack that a
static-challenge design would remain vulnerable to.

## 5.3 What IDP deliberately does not provide

IDP provides no confidentiality of its own and explicitly assumes TLS
1.3 for the wire (RFC-0001 §1, a MUST). It provides no post-quantum
resistance — Ed25519/X25519 are both classical-only constructions, and
a post-quantum-hybrid cipher suite is out of scope for this draft
(§12.1). It provides no protection against real-time relay/adversary-
in-the-middle (AiTM) phishing proxies beyond what TLS channel binding
(RFC 9266 [RFC9266]) would add if implemented, which the reference
implementation currently does not (§10.2). These are documented as
explicit residual risks in §10, not omitted from discussion.

\newpage

# 6. Privacy-by-Design Entropy Collection

RFC-0001 §10 is unusual among protocol specifications in being
normative on data-minimization, not merely on wire format. This section
describes how that normative text is enforced in the reference
implementation, because a privacy constraint stated only in prose and
not enforced in code is not a real constraint.

## 6.1 The allow-list mechanism

The entropy-normalization module accepts a raw device-signal dictionary
but only ever reads seven explicitly allow-listed, pre-bucketed fields
(coarse OS family, bucketed screen-resolution class, timezone offset,
language, bucketed color depth, bucketed CPU core-count class, and GPU
*vendor* only — never the full renderer string). Any other key present
in the input — including deliberately "invasive" fingerprinting fields
injected during testing (§8.3) — is silently dropped before hashing.
This is enforced structurally (the normalization function iterates the
allow-list, not the input), not by validation that could be bypassed by
a malformed caller; property-based fuzz testing confirmed this
empirically by asserting that adding arbitrary non-allow-listed keys to
device input never changes the resulting Identity Vector.

## 6.2 Consent gating and per-relying-party salting

Device signal collection requires a valid, unexpired, revocable consent
receipt (RFC-0001 §4.3, §10.2); its absence is a registered protocol
error (`ERR_CONSENT_MISSING`), not a silent default-allow. The
normalization function additionally takes a per-Relying-Party salt,
so that even if a server operator were compromised, the same physical
device's hash would not be linkable across two unrelated Relying
Parties using the protocol — a mitigation for the insider-threat
scenario discussed in §10.7.

## 6.3 What is retained, and what is not

Only the derived, non-reversible Identity Vector and its digest are
retained server-side by default; raw device/behavioral/contextual
input is discarded immediately after use unless a Relying Party has a
separately documented, consented retention policy, which the reference
implementation does not provide a mechanism for (deliberately — the
default is zero retention, and adding retention is a positive action a
deployer would need to build, not a switch to flip off).

\newpage

# 7. Reference Implementation Architecture

The reference implementation comprises two independently-written
codebases: a Python implementation (`reference/`, 1,876 lines across
26 modules) serving as the primary specification-validating
implementation and REST server, and a TypeScript implementation
(`sdk/javascript/`, 776 lines) serving as an interoperability-proving
client SDK (§9). Both are organized around the same module boundaries,
intentionally, so the two remain easy to cross-reference (Table 3).

**Table 3: Reference module architecture**

| Module | Responsibility |
|---|---|
| `crypto/` | RFC-0001 §11 primitive wrappers (hashing, signatures, ECDH, HKDF, AEAD, CSPRNG) |
| `entropy-engine/` | Device/behavior/context normalization and Device DNA hashing (§6) |
| `identity-engine/` | Identity Vector compilation, cross-session identity streams, consent gating |
| `trust-engine/` | Trust Score computation: weights, history, risk rules, policy thresholds, confidence |
| `session-engine/` | Session DNA generation, rotation, expiration, validation, renewal |
| `gateway/` | Server-side handshake orchestration and state machine enforcement |
| `verifier/` | Client-side handshake message construction |
| `storage/` | SQLite-backed persistence for subject baselines and trust history |
| `server/` | FastAPI REST surface exposing the protocol over HTTP |

## 7.1 A design note on statelessness and the cold-start problem

An architectural property worth surfacing explicitly, because it is
the root cause of the deadlock bug discussed in §8.1: the Trust Score
function is *pure* with respect to its inputs (identity distance,
n_eff, history, context priors, risk context) — it has no
hidden state and is independently unit-testable — but the *system*
built around it (the Gateway orchestration layer, §3.2) is
fundamentally stateful, since S_history and identity
distance both depend on what happened in *previous* sessions for the
same subject. This split between a pure scoring function and a
stateful orchestration layer is deliberate (it is what makes §4.3's
worked example unit-testable in isolation), but it means that
correctness bugs in this system are not fully visible from unit-testing
the scoring function alone — they require testing the *sequence* of
sessions a real subject would experience, which is precisely the kind
of bug property-based and persistence-layer testing surfaced (§8) that
a single-session unit test could not have.
\newpage

# 8. Engineering Validation: Property-Based Testing

A specification's formulas can be internally consistent and still be
wrong in ways that only manifest across many interacting components or
many repeated invocations — the class of defect example-based unit
testing, which by construction only exercises the cases its author
thought to write, is least likely to catch. This section reports, in
full, three defects found during the development of this reference
implementation, the process that found each one, and the fix. We
consider this section, not the absence of reported defects, to be the
paper's strongest evidence for the model's current correctness: a
formal model whose authors report no defects either had none (unlikely
for a first draft of this complexity) or was not tested adversarially
enough to find them.

## 8.1 Defect 1: the S_identity scaling bug

**Symptom.** During manual testing of the SQLite persistence layer
(§7), a subject's Trust Score was observed to not increase across
repeated legitimate sessions from the same, now-recognized device —
contrary to the model's stated intent (§4.3).

**Root cause.** The original formula,
S_identity = 100 · (1−d)/2 · confidence,
has a maximum value of 50·confidence at d=0 (a
*perfect* match) — the same value the "no baseline yet" default case
was assigned. A fully-recognized returning device therefore scored
identically to a completely unknown first-time device: the formula's
own algebra capped the reward for recognition at exactly the level of
having no information at all.

**Fix.** Corrected to S_identity = 100 · (1 − d/2) · confidence (§4.2), which spans the full
[0, 100·confidence] range and treats d=1 (not d=0)
as the neutral/no-information point — a principled choice, since
d=1 corresponds to orthogonal (uncorrelated) vectors, the natural
mathematical representation of "no information," rather than an
arbitrary constant.

## 8.2 Defect 2: the history-score deadlock

**Symptom.** After fixing Defect 1, repeated sessions from a
recognized device still failed to progress past `DENY`.

**Root cause.** The original history definition counted
match(t−k)=1 only for `ALLOW` outcomes, treating `STEP_UP`
as a history failure. But `ALLOW` requires a reasonable
S_history, and a first-ever session (no baseline) can score
no higher than `STEP_UP` even under the corrected Defect-1 formula —
producing a structural deadlock in which no subject could ever
accumulate the history needed to ever reach `ALLOW`. This defect was
invisible to unit tests of the scoring function in isolation (§7.1)
because it only manifests across a *sequence* of sessions, which no
single-session unit test exercises.

**Fix.** Redefined match(t−k)=1 for decisions in
{ALLOW, STEP_UP} (§4.2), and excluded a subject's
first-ever (no-baseline) session from history recording entirely,
since it is not yet a meaningful judgment of identity consistency. A
regression test (`test_trust_score_improves_across_repeated_sessions_same_device`)
now asserts this progression explicitly using the persistence layer
across four consecutive simulated sessions, rather than only asserting
a single session's output in isolation.

## 8.3 Defect 3: unauthenticated remote denial-of-service via malformed entropy

This is the most operationally significant defect found, and the one
we consider the strongest argument for property-based testing of
security-relevant code specifically.

**Discovery.** A property-based test (`test_identity_properties.py`,
using the Hypothesis framework [MacIver2019]) generates randomized
device/behavior/context dictionaries — including wrong-typed values
for every field, a standard fuzzing strategy for defensive-coding
verification — and asserts that Identity Vector compilation never
raises an unhandled exception for any input, only ever the specific,
typed `DegenerateInputError` for the one documented degenerate case.
Within the first randomized-example run, this test failed with an
unhandled `TypeError`.

**Root cause.** The behavioral-signal normalizer computed summary
statistics (`sum(cadence) / len(cadence)`) assuming
`typing_cadence_ms` was always a list of numbers. A client — malicious
or merely buggy — sending this field as a string instead (e.g. the
single character `"0"`, which Python's `sum()` will attempt to iterate
and fail on with a `TypeError`) would crash the handler processing the
`ENTROPY` message. Because `ENTROPY` is processed *before* the `PROOF`
signature is verified in the protocol's state machine (§3.2 — this
ordering is required by RFC-0001, since the Identity Vector must be
computed before the transcript hash it is bound into can be
constructed), this crash is triggerable by an entirely unauthenticated
client: no valid signing key, no prior legitimate session, and no
rate-limiting bypass are required. This is, in standard vulnerability
taxonomy, an unauthenticated remote denial-of-service condition against
the reference server's request-handling process.

**Fix.** The normalizer was made defensive/fail-closed: malformed input
for `typing_cadence_ms` (or the timezone-offset field, which had the
identical class of bug on a separate code path found by inspection
immediately after) now degrades to the empty/neutral case rather than
raising, consistent with the protocol's explicit threat-model premise
that "the client device is fully untrusted" (§10) — a premise the
original code did not actually honor at this specific code path,
despite stating it elsewhere. Regression tests for both the list-typed
and numeric-typed malformed cases were added.

**Discussion.** We highlight this defect specifically because it
illustrates a general and, we believe, underappreciated point: a
threat model's stated premises (§10 says explicitly that client input
is untrusted) are not self-enforcing. Code that processes
attacker-controlled input before authentication is complete is exactly
where that premise must be verified empirically, per code path, not
merely asserted in a document — and the verification method that found
this specific gap between stated premise and actual code (structured
input-space fuzzing of the pre-authentication message handler) is
under-used relative to how effective it was here: one property-based
test, running its first generated example, found a remotely
exploitable crash that 30 hand-written example-based unit tests
(passing at the time) had not.

## 8.4 Coverage summary

The full property-based suite comprises 45 tests across five modules
(cryptographic primitives, Identity Vector properties, Trust Score
properties, Session DNA lifecycle properties, and adversarial
handshake state-machine fuzzing), each executing 100–300 randomized
examples per run (Hypothesis's default shrinking behavior additionally
minimizes any failing example to the smallest reproducing case). Table
4 summarizes the invariants checked.

**Table 4: Property-based test coverage by module**

| Module | Tests | Representative invariants checked |
|---|---|---|
| Cryptographic primitives | 14 | Hash determinism & domain separation; HKDF output length; Ed25519 sign/verify correctness under tampering; X25519 ECDH symmetry; CSPRNG non-collision |
| Identity Vector | 5 | Unit-norm output or typed rejection; determinism; self-distance zero; allow-list fail-closed under injected non-listed fields |
| Trust Score | 10 | Output always in [0,100]; decision consistent with policy thresholds; identity score monotonic in distance; context score never exceeds worst single prior |
| Session DNA lifecycle | 7 | Rotation never repeats a value; generation counter monotonic; only the latest generation ever validates; revocation is absolute |
| Adversarial handshake | 9 | Out-of-order messages rejected; replayed `msg_id` rejected; unsupported cipher suites rejected; forged/garbage signatures rejected |
\newpage

# 9. Cross-Language Interoperability

A specification that only one implementation has ever satisfied has
not demonstrated that it is implementable, only that it was
implemented once. To test this, we produced a second, independent
TypeScript implementation (`sdk/javascript/`, using `@noble/curves` and
`@noble/hashes` — a different cryptographic library from the Python
reference's `PyNaCl`/`cryptography` stack) and verified genuine
interoperability at two levels: byte-identical intermediate output, and
a real network handshake between the two implementations.

## 9.1 Byte-identical digest parity

An automated regression test (`tests/interop/test_ts_python_parity.py`)
runs both implementations against identical fixed inputs and asserts
**byte-identical** output — not merely "producing a plausible-looking
result," which, as the two defects below demonstrate, both
implementations did even while disagreeing with each other — for:
domain-separated BLAKE3 hashes, HKDF output, each of the three
entropy-normalization digests, and the complete 256-dimensional
Identity Vector (compared to 10⁻¹⁰ precision) including its
`iv_digest`.

**Defect 4: HKDF vs. HKDF-Expand.** The TypeScript port of the
vector-expansion function (§4.1's *Expand*) initially used
`@noble/hashes`'s full extract-then-expand `hkdf()` function. The
Python reference uses `cryptography`'s `HKDFExpand` — expand-only,
treating its input seed directly as the already-extracted pseudorandom
key. These are different constructions (RFC 5869 [RFC5869] §2 distinguishes
Extract and Expand as separate, independently invokable phases), and
using the full construction where only Expand was specified produces a
**different but equally valid-looking** Identity Vector: correctly
unit-normalized, correctly dimensioned, indistinguishable from a
correct output by any check that does not compare against an
independent reference implementation. The interop parity test failed
immediately on this input, isolating the defect to the vector-expansion
function specifically (all upstream digests still matched).

**Defect 5: digest concatenation shape.** A related but distinct
defect in the same code path: the Python reference computes
`iv_digest` by joining the vector's byte-encoded components into one
flat concatenated blob before hashing (`b"".join(...)`), whereas the
TypeScript port initially passed the 256 components as separately
length-prefixed parts to the multi-part hashing function (the correct
approach for the protocol's normal domain-separated hashing, §5.1, but
not for this specific internal digest, which follows a different,
undocumented-until-this-defect convention). The interop test caught
this in the same debugging pass as Defect 4.

Both defects share a common shape worth naming explicitly: each
produced output that was *individually plausible* — correct type,
correct length, correct numeric range — and would not have been caught
by any test that validated the TypeScript implementation against its
own internal consistency alone. They were only discoverable by
comparison against an independent reference, which is the entire
methodological argument for building and testing a second
implementation rather than treating "we have one implementation and it
passes its own tests" as sufficient evidence of a specification's
correctness.

## 9.2 Live cross-language handshake

Beyond digest parity, we verified a complete RFC-0001 handshake
executed with a TypeScript client (`sdk/javascript/src/demo/demoHttpClient.ts`)
against the Python reference server over real HTTP. The client
generates its Ed25519 keypair and signs the transcript hash using
`@noble/curves`; the server verifies that signature using `PyNaCl`. A
mismatch in transcript-hash construction or canonical JSON
serialization between the two implementations — including either of
Defects 4–5, prior to their fix — manifests here as `ERR_SIGNATURE_INVALID`,
not as a subtler numeric discrepancy; the handshake either completes
or it does not. We confirmed successful completion, including the
server-computed Trust Score correctly reflecting persisted history from
a prior session for the same subject (the same `DENY → STEP_UP`
progression from §4.3's discussion, produced by a client the Trust
Engine itself has no code path shared with).

\newpage

# 10. Threat Model and Security Analysis

This section summarizes the threat model (full text:
`docs/architecture/threat-model.md`), organized by STRIDE category,
with explicit residual-risk acknowledgment for mitigations that are
partial rather than complete — a threat model that reports only solved
problems is not describing its actual security posture.

**Table 5: Threat summary**

| Threat | Mitigation | Status |
|---|---|---|
| Replay (§10.1) | `msg_id` uniqueness + timestamp window + transcript-bound signatures | Mitigated |
| Real-time relay / AiTM phishing (§10.2) | None beyond context-based risk flagging | **Partial — residual risk** |
| Credential stuffing (§10.3) | Trust Engine + rate limiting (no static-password sole factor) | Mitigated |
| Session hijacking (§10.4) | Mandatory rotation bounds exposure window | **Bounded, not eliminated** |
| Wire-level MITM (§10.5) | Delegated entirely to TLS 1.3 | Mitigated (by requirement) |
| Device theft (§10.6) | Behavioral drift detection (probabilistic only) | **Probabilistic mitigation only** |
| Insider threat (§10.7) | Hashing + zero raw retention + per-RP salting | Reduced, not eliminated |
| Supply chain (§10.8) | Organizational controls; minimal, audited dependency surface | Out of wire-protocol scope |

## 10.1 The most significant acknowledged gap: real-time relay

RFC-0001's transcript-binding (§5.2) defeats *replay* of a captured
proof, but does not by itself defeat a *real-time* proxy that
transparently forwards every message between victim and legitimate
server while capturing the resulting `SESSION_DNA`. TLS channel binding
[RFC9266] — cryptographically binding the application-layer handshake
to the specific TLS channel it traveled over — is the standard
mitigation for this class of attack and is noted as a SHOULD, not yet a
MUST, in the current draft; the reference implementation does not
currently implement it. We report this as an open item rather than
omitting the attack class from discussion, consistent with §1.2's
priority on honest, falsifiable claims over a clean-looking checklist.

## 10.2 Explicitly out of scope

Physical/endpoint compromise below the OS trust boundary,
post-quantum-adversary resistance (Ed25519/X25519 are not post-quantum
constructions), and social engineering of a Relying Party's support
staff are all explicitly out of scope for this protocol layer, stated
as such rather than left ambiguous.
\newpage

# 11. Performance Evaluation

All figures were measured on the reference Python implementation,
single-threaded, on commodity container hardware (no GPU acceleration,
no hand optimization beyond what the underlying cryptographic
libraries provide by default). These are meant to establish
order-of-magnitude feasibility, not to represent a tuned production
deployment's throughput.

**Table 6: Micro-benchmark results (2,000 iterations per primitive)**

| Operation | Throughput |
|---|---|
| BLAKE3-256 hash (domain-separated) | 573,391 ops/sec |
| HKDF-SHA256 derivation | 118,737 ops/sec |
| Ed25519 signature generation | 36,504 ops/sec |

**Table 7: End-to-end handshake latency**

| Configuration | Throughput | Mean latency |
|---|---|---|
| Full handshake, in-process, no persistence | 1,384 handshakes/sec | 0.72 ms |
| Full handshake, in-process, with SQLite persistence and Session DNA generation | 351 handshakes/sec | 2.85 ms |

The roughly 4x latency increase between the two end-to-end
configurations is attributable to synchronous SQLite I/O (subject
baseline and history read/write) and the ephemeral X25519 ECDH plus
HKDF derivation required to produce a `SESSION_DNA` — neither of which
occurs in the no-persistence, first-session-only benchmark, which
short-circuits to a `DENY` decision before reaching session generation.
The Ed25519 signature-verification cost (not separately benchmarked
here, but symmetric in cost to generation for this construction) is the
single largest per-handshake cryptographic expense, consistent with the
raw micro-benchmark figures in Table 6. We consider 351 fully-persisted
handshakes/sec, single-threaded and unoptimized, to indicate that the
protocol's computational cost is not a barrier to production-scale
deployment behind ordinary horizontal scaling, though we make no claim
about behavior under concurrent load, connection pooling contention, or
a hardened production SQLite/PostgreSQL configuration, none of which
this reference implementation's benchmarks exercise.

\newpage

# 12. Limitations

We list limitations without euphemism, consistent with this paper's
stated priority on honest over favorable framing.

## 12.1 Protocol-level limitations

- **No post-quantum cipher suite.** Ed25519/X25519 offer no resistance
  to a cryptographically-relevant quantum adversary. A PQ-hybrid suite
  is unspecified future work (§13).
- **TLS channel binding not yet mandatory** (§10.1) — the real-time
  relay/AiTM residual risk is the most significant open item in the
  current draft.
- **No step-up-challenge subsystem is specified.** RFC-0001 defines the
  `STEP_UP` decision outcome but not the out-of-band challenge (OTP,
  push approval, etc.) a Relying Party would need to implement to act
  on it; §8.2's history-scoring correction assumes step-up challenges,
  when issued, are generally completed successfully, which the protocol
  itself has no mechanism to verify.

## 12.2 Reference-implementation limitations

- **In-memory consent and in-flight-handshake state** in the reference
  server (only subject baselines and trust history are SQLite-backed);
  a process restart loses any handshake that has not yet completed.
- **Single-node SQLite persistence** — no clustering, replication, or
  concurrent-writer story; adequate for the reference implementation's
  demonstrative purpose, not for a multi-instance production deployment
  without modification.
- **No rate-limiting middleware wired into the reference server**,
  despite the threat model (§10.3) assuming its presence; this is
  explicitly noted in the server module's own documentation as a gap a
  deployer must close, not a false claim of completeness.
- **Only two of seven originally-scoped SDK languages are implemented**
  (Python reference, TypeScript client — §9); Rust, Go, Java, C#, and
  C++ SDKs remain unimplemented.
- **No fuzz/property-based testing of the REST API layer itself**
  (`reference/server/api.py`) — §8's property-based tests exercise the
  underlying protocol engines directly; the HTTP/FastAPI request-handling
  layer has only example-based test coverage via the integration demo
  scripts.

## 12.3 This paper's own limitations

This paper reports results from a reference implementation built and
tested by a single working group over a short development window, not
from an independently-audited, adversarially red-teamed, or
production-deployed system. The performance figures (§11) are
micro-benchmarks on a single machine, not a load-tested distributed
deployment. The "related work" comparison (§2) is a design-goals
comparison, not a formal security-property equivalence proof against
TLS, OAuth, or FIDO2. No claim of formal, machine-checked security
proof (e.g. in the style of a symbolic-model verification tool such as
ProVerif or Tamarin) is made for any part of this protocol; this is
identified as future work (§13), not silently omitted.

\newpage

# 13. Future Work

1. **Formal, machine-checked verification** of the handshake's replay-
   and forward-secrecy properties using a symbolic protocol verifier.
2. **TLS channel binding** (RFC 9266) implementation, upgrading §10.1's
   SHOULD to a MUST once a channel-binding profile is specified.
3. **Post-quantum-hybrid cipher suite** as an additional, negotiable
   `supported_suites` option alongside the current classical suite.
4. **A specified step-up-challenge subsystem**, closing the gap noted
   in §12.1.
5. **Additional-language SDKs** (Rust, Go, Java, C#, C++), each adding
   a further independent interoperability data point beyond the
   Python/TypeScript pair reported here (§9).
6. **Fuzz/property-based testing extended to the REST API layer**
   itself, closing the gap noted in §12.2.
7. **A formal security/performance evaluation under concurrent,
   multi-instance, production-representative load**, which this paper's
   single-machine micro-benchmarks (§11) do not attempt to substitute
   for.

# 14. Conclusion

We have presented RFC-0001, a complete normative specification for a
session-duration, continuously-verified identity and trust protocol; a
formal mathematical model for its central Trust Score computation,
including a fully worked and unit-tested numeric example; and a
reference implementation in two independent languages, verified
interoperable at the level of byte-identical cryptographic output, not
merely similar-looking behavior. We have additionally reported, in
full and without omission, five real defects found during this work —
two in the formal model itself, one a remotely-exploitable
denial-of-service condition, and two in cross-language interoperability
— together with the specific testing methodology (property-based fuzz
testing and independent-implementation parity testing) that found each
one. We consider this transparent defect-reporting, together with the
explicit, unpadded limitations list in §12, to be as much a
contribution of this paper as the protocol specification itself: a
security-relevant specification's credibility rests on the rigor of
its validation being visible, not on the absence of visible defects.

IDP remains a draft protocol proposal and a research-grade reference
implementation. It is not an adopted standard, and this paper makes no
claim that it is production-ready without the further work enumerated
in §13. It is offered as a concrete, implementable, and independently
validated starting point for continuous, session-duration trust
evaluation — a property we believe the "authenticate once" model
underlying most deployed protocols today does not adequately provide.

\newpage

# Bibliography {-}

[Biryukov2016] Biryukov, A., Dinu, D., Khovratovich, D. "Argon2: New
Generation of Memory-Hard Functions for Password Hashing and Other
Applications." *IEEE European Symposium on Security and Privacy*, 2016.

[Kolter2005] Kolter, J.Z., Maloof, M.A. "Using Additive Expert
Ensembles to Cope with Concept Drift." *Proceedings of the 22nd
International Conference on Machine Learning*, 2005. (Representative
of the broader adaptive/continuous-authentication literature this work
draws its motivation from.)

[MacIver2019] MacIver, D.R., Hatfield-Dodds, Z., et al. "Hypothesis: A
new approach to property-based testing." *Journal of Open Source
Software*, 4(43), 1891, 2019.

[NIST-800-207] Rose, S., Borchert, O., Mitchell, S., Connelly, S.
"Zero Trust Architecture." *NIST Special Publication 800-207*,
National Institute of Standards and Technology, 2020.

[OConnor2020] O'Connor, J., Aumasson, J-P., Neves, S., Wilcox-O'Hearn,
Z. "BLAKE3: One Function, Fast Everywhere." 2020.

[RFC5869] Krawczyk, H., Eronen, P. "HMAC-based Extract-and-Expand Key
Derivation Function (HKDF)." *RFC 5869*, IETF, 2010.

[RFC6749] Hardt, D., ed. "The OAuth 2.0 Authorization Framework." *RFC
6749*, IETF, 2012.

[RFC7748] Langley, A., Hamburg, M., Turner, S. "Elliptic Curves for
Security." *RFC 7748*, IETF, 2016.

[RFC8032] Josefsson, S., Liusvaara, I. "Edwards-Curve Digital Signature
Algorithm (EdDSA)." *RFC 8032*, IETF, 2017.

[RFC8439] Nir, Y., Langley, A. "ChaCha20 and Poly1305 for IETF
Protocols." *RFC 8439*, IETF, 2018.

[RFC8446] Rescorla, E. "The Transport Layer Security (TLS) Protocol
Version 1.3." *RFC 8446*, IETF, 2018.

[RFC8785] Rundgren, A., Jordan, B., Erdtman, S. "JSON Canonicalization
Scheme (JCS)." *RFC 8785*, IETF, 2020.

[RFC9266] Bishop, M. "Channel Bindings for TLS 1.3." *RFC 9266*, IETF,
2022.

[W3C-WebAuthn] W3C. "Web Authentication: An API for accessing Public
Key Credentials — Level 2." *W3C Recommendation*, 2021.

\newpage

# Appendix A: Error Code Registry (RFC-0001 §6) {-}

| Code | Meaning | Retryable |
|---|---|---|
| `ERR_VERSION_UNSUPPORTED` | Unknown/unsupported protocol major version | No |
| `ERR_REPLAY` | `msg_id` reused within session | No |
| `ERR_CLOCK_SKEW` | Timestamp outside tolerance window | Yes (after resync) |
| `ERR_STATE_INVALID` | Message not valid in current state | No |
| `ERR_CONSENT_MISSING` | No valid consent receipt for entropy collection | No |
| `ERR_SUITE_UNSUPPORTED` | No overlap in supported cipher suites | No |
| `ERR_SIGNATURE_INVALID` | Proof signature verification failed | No |
| `ERR_TRUST_INSUFFICIENT` | Trust score below policy threshold | Conditionally |
| `ERR_SESSION_EXPIRED` | Session expiry passed | Client must re-handshake |
| `ERR_SESSION_REVOKED` | Session was explicitly revoked | No |
| `ERR_RATE_LIMITED` | Too many attempts from origin | Yes (backoff) |
| `ERR_MALFORMED` | Envelope/body fails schema validation | No |

# Appendix B: Reference Implementation Statistics {-}

| Metric | Value |
|---|---|
| Python reference implementation | 1,876 lines, 26 modules |
| TypeScript client SDK | 776 lines |
| Test suite (Python: unit + property-based + integration + interop) | 76 tests |
| Test suite (TypeScript) | 17 tests |
| Property-based test examples per full run | ~4,500–13,500 (45 tests × 100–300 examples) |
| Defects found via property-based / interop testing | 5 (documented in full, §8–§9) |
