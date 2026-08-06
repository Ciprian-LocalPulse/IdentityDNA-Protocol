# `IdentityStream` — Data Structure

See RFC-0001 §2 (Terminology) and §7 (Identity Vector). Implemented at
`reference/identity-engine/identity_stream.py`.

```json
{
  "session_id": "b55ff2ce-0b16-40e6-a8da-6b442d36a732",
  "samples": [
    {
      "identity_vector_id": "712b9b3f-67ca-4401-905f-a746f25463bd",
      "iv_digest": "e8cb5586f2bca4ca...",
      "captured_at": "2026-08-05T02:10:00Z"
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `session_id` | uuid | Binds the stream to one Session DNA lifecycle |
| `samples[].identity_vector_id` | uuid | See `identity-vector.md` |
| `samples[].iv_digest` | hex(32) | Digest of the full 256-dim vector, sent in `IDENTITY_ACK` |
| `samples[].captured_at` | RFC-3339 | Server-assigned capture timestamp |

The raw 256-float vector is **never serialized to the wire** — only the
digest travels in `IDENTITY_ACK` (RFC-0001 §4.4). The full vector stays
server-side for distance computation against the enrolled baseline.
