# IdentityDNA Protocol — Specification v0.1 (Draft)

Status: Alpha / Draft — subject to change without notice.

## 1. Scope
This document specifies the core message flows, data structures, and behavioral requirements of IdentityDNA Protocol (IDP) version 0.1.

## 2. Terminology
- **Identity Stream** — a continuous, deterministic sequence of identity vectors derived from session entropy.
- **Session DNA** — a unique, ephemeral cryptographic identity bound to a single session.
- **Trust Score** — a numeric, adaptive measure of confidence that the current session is controlled by its legitimate participant.
- **Entropy Source** — any input (device, behavioral, contextual, environmental) contributing randomness/uniqueness to the Identity Stream.

## 3. Protocol Flow (Summary)
1. Client initiates a session and begins entropy collection.
2. Client derives an Identity Stream from collected entropy.
3. Server issues a Session DNA upon successful initial verification.
4. Client and server continuously exchange/verify Identity Stream updates.
5. Trust Engine adjusts the Trust Score based on incoming signals.
6. Access is granted, maintained, degraded, or revoked based on the Trust Score and Session DNA validity.

## 4. Normative References
See `docs/protocol/` for detailed component specifications: handshake, identity-stream, trust-engine, entropy-engine, session-dna, and verification.

## 5. Status of This Document
This is a v0.1 draft. It is intentionally incomplete in places pending further design work, most notably in `docs/mathematics/` (formal entropy and proof models) and `docs/whitepaper/` (full academic treatment).
