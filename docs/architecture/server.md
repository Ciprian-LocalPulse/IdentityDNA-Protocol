# Server Architecture

The server hosts the Trust Engine, Verification Engine, and Session Engine, and is responsible for issuing and validating Session DNA.

## Responsibilities
- Verify incoming Identity Stream updates against expected session state.
- Continuously score trust and adjust access accordingly.
- Issue, renew, and invalidate Session DNA.
- Expose a gateway/API surface for integrating applications.

## Status
Draft — reference implementation planned under `reference/server/`, `reference/gateway/`, `reference/verifier/`, `reference/trust-engine/`, and `reference/session-engine/`.
