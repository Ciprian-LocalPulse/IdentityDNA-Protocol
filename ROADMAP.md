# Roadmap

IdentityDNA Protocol is being developed in eight phases. Each phase builds on the previous one and moves the project from a written proposal toward a reviewed, implemented, and audited standard.

## Phase 1 — Protocol Specification
Define the core protocol: identity streams, entropy sources, session DNA, trust engine behavior, and the handshake/verification flow. Output: `docs/specification/` and `docs/protocol/`.

## Phase 2 — Reference SDK
Build client-side SDKs (starting with Python and JavaScript, expanding to Go, Rust, Java, and .NET) implementing identity stream generation and session participation.

## Phase 3 — Reference Server
Build the server-side verification and trust-engine components needed to validate identity streams and issue/verify Session DNA.

## Phase 4 — Developer API
Publish a stable, documented API surface so third-party applications can integrate IdentityDNA Protocol without needing to understand its internals.

## Phase 5 — Browser SDK
Bring identity stream generation to the browser, accounting for the constraints and entropy sources available in a web context.

## Phase 6 — Mobile SDK
Extend the SDK to iOS and Android, leveraging device-level entropy and secure hardware where available.

## Phase 7 — Academic Publication
Formalize the protocol's design, threat model, and security analysis into a peer-reviewable academic paper.

## Phase 8 — Independent Security Audit
Commission an independent, third-party security audit of the specification and reference implementation before recommending production use.

---

Progress against this roadmap is tracked in [`CHANGELOG.md`](CHANGELOG.md).
