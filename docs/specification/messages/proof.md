# `PROOF` — Data Structure

See RFC-0001 §4.5, §11.2.

```json
{ "signature": "base64(Ed25519 sig over transcript_hash)", "public_key": "base64(32 bytes)" }
```

`transcript_hash = BLAKE3("IDP-TRANSCRIPT-v1" || HELLO || CHALLENGE || ENTROPY || IDENTITY_ACK)`,
computed by `reference/identity-engine/verification.py::compute_transcript_hash`.
