# Client Architecture

The client is responsible for the Identity Engine and Entropy Engine: collecting entropy and deriving the Identity Stream sent to the server for verification.

## Responsibilities
- Collect entropy from available, platform-appropriate sources.
- Derive and continuously update the Identity Stream.
- Maintain and present the current Session DNA to the server as required.
- Respect user privacy and platform constraints (see `ETHICS.md`).

## Status
Draft — reference implementation planned under `reference/client/` and SDKs under `sdk/`.
