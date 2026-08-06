# Identity Stream

An Identity Stream is a continuous, deterministic sequence of identity vectors derived from multiple entropy sources tied to a session.

## Properties
- **Deterministic**: given the same underlying entropy sources and derivation function, the stream is reproducible for verification purposes, without exposing the raw entropy itself.
- **Continuous**: the stream is not a single value checked once, but a sequence produced throughout the session.
- **Bound to session**: an Identity Stream has no meaning or validity outside the session it was generated for.

## Sources
Identity vectors are derived from entropy supplied by the Entropy Engine (see `entropy-engine.md`), which may include device signals, behavioral patterns, contextual data, and environmental factors.

## Open Questions
- Exact vector derivation function (candidate constructions under evaluation — see `docs/mathematics/identity-vector.md`).
- Update frequency and its tradeoffs between security and performance.
- Handling of degraded/low-entropy environments (e.g., constrained IoT devices).
