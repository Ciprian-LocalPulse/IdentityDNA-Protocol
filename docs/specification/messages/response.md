# `TRUST_RESULT` / `SESSION_DNA` — Server Response Pair

These two messages (RFC-0001 §4.6-§4.7) are always emitted together in
response to a valid `PROOF`, except when `decision == DENY`, in which
case no `SESSION_DNA` is issued (see `reference/gateway/handshake.py::handle_proof`).

See `trust-score.md` and `session-dna.md` for the individual schemas.
