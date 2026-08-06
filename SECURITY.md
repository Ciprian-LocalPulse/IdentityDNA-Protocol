# Security Policy

IdentityDNA Protocol is a research-stage authentication framework. This document describes the current threat model, known limitations, attack surface, and how to responsibly report security issues.

We deliberately avoid claiming this protocol is "unbreakable" or "impossible to hack." No authentication system can honestly make that claim. Instead, this document aims to be precise about what the protocol is designed to resist, what it assumes, and where it is currently weak or unproven.

## 1. Threat Model

IdentityDNA Protocol is designed with the following adversaries in mind:

- **Network attackers** attempting to intercept, replay, or tamper with session data in transit.
- **Session hijackers** attempting to reuse a captured identity stream or session DNA outside its intended window.
- **Credential-stuffing / brute-force actors** targeting static entry points.
- **Malicious or compromised clients** attempting to forge identity vectors.

The protocol currently does **not** claim protection against:

- A fully compromised endpoint under the attacker's total control (e.g., a rooted device with a malicious agent reading memory in real time).
- Nation-state-level side-channel attacks.
- Social engineering of the end user.

## 2. Known Limitations

- The protocol is at **Alpha (v0.1)** stage. It has not undergone independent security review.
- Entropy source quality and diversity directly affect the strength of identity vectors; weak or predictable entropy sources degrade security guarantees.
- The trust engine's scoring model is heuristic and will require empirical tuning and adversarial testing before it can be relied upon in high-assurance environments.
- No formal cryptographic proof of the protocol's security properties has yet been published (see `docs/mathematics/proof.md`, currently in progress).

## 3. Attack Surface

- Client-side identity/entropy collection logic.
- Transport between client and verification engine.
- Trust engine scoring inputs and thresholds.
- Session DNA issuance and expiry logic.
- Any reference SDK or CLI implementation.

## 4. Security Assumptions

- The underlying transport channel provides confidentiality and integrity (e.g., TLS).
- The verifying server is not itself compromised.
- Cryptographic primitives used are implemented correctly and kept up to date.

## 5. Responsible Disclosure

If you discover a security vulnerability in the specification or reference implementation, please report it privately rather than opening a public issue.

**Contact:** contact@agentflow-enterprise.com

Please include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce, if applicable.
- Any suggested mitigation, if you have one.

We will acknowledge reports as promptly as possible and aim to keep reporters informed as an issue is investigated and addressed.

## 6. Status

This project has **not** undergone an independent security audit. Phase 8 of the [Roadmap](ROADMAP.md) is dedicated specifically to this. Until that milestone is reached, IdentityDNA Protocol should be treated as experimental and should not be relied upon for production security decisions.
