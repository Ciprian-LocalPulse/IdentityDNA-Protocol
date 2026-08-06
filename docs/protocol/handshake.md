# Handshake

Describes the initial exchange between client and server that bootstraps a session before continuous identity streaming begins.

## Goals
- Establish a secure channel (assumed: TLS or equivalent transport security).
- Perform an initial identity check before any Session DNA is issued.
- Negotiate protocol version and capabilities between client and server.

## Flow (Draft)
1. Client sends a session initiation request, including supported protocol version and initial entropy snapshot.
2. Server validates the request and responds with a session challenge.
3. Client responds to the challenge using its Identity Engine output.
4. Server verifies the response and, if successful, issues an initial Session DNA (see `session-dna.md`) and begins Trust Engine evaluation.

This flow is a draft and will be refined alongside the formal specification in `docs/specification/`.
