# Verification

Describes how a server verifies an Identity Stream and Session DNA without needing to learn the user's underlying secrets — a zero-knowledge-oriented approach.

## Goals
- Confirm the Session DNA presented is valid, unexpired, and matches the expected session.
- Confirm the current Identity Stream is consistent with the trust threshold required for the requested action.
- Avoid the verifier needing to store or learn raw entropy/identity secrets.

## Flow (Draft)
1. Client presents current Session DNA and Identity Stream state.
2. Verification Engine checks Session DNA validity (issuance, expiry, session binding).
3. Verification Engine checks consistency of the Identity Stream against the Trust Engine's current score.
4. Access is granted, denied, or challenged based on the outcome.

## Status
Draft. Formal zero-knowledge proof construction is pending and tracked in `docs/mathematics/proof.md`.
