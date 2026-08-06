# `SessionDNA` — Data Structure

See RFC-0001 §4.7, §9. Implemented at `reference/session-engine/generator.py`.

```json
{
  "session_id": "b55ff2ce-0b16-40e6-a8da-6b442d36a732",
  "sdna": "base64(32 bytes)",
  "issued_at": "2026-08-05T02:10:05Z",
  "expires_at": "2026-08-05T02:15:05Z",
  "rotation_interval_s": 300,
  "generation": 0
}
```

`generation` increments on every rotation (`VERIFY` round). A validator
MUST reject any `generation` older than the current one — see
`reference/session-engine/validator.py::SessionStore.validate`.
