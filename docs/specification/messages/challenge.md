# `CHALLENGE` — Data Structure

See RFC-0001 §4.2.

```json
{
  "selected_suite": "ed25519-blake3-argon2id",
  "server_nonce": "base64(32 bytes)",
  "challenge": "base64(32 bytes)",
  "difficulty": 0,
  "server_eph_public": "base64(32 bytes, X25519)"
}
```

`difficulty > 0` triggers the optional proof-of-work anti-flood mechanism
(RFC-0001 §11.4) — not a security boundary, only a cost multiplier.
