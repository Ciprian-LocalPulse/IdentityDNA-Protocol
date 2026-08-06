# `TrustResult` — Data Structure

See RFC-0001 §4.6 and `docs/mathematics/formal-model.md` §3. Implemented
at `reference/trust-engine/score.py::TrustResult`.

```json
{
  "trust_score": 92.4,
  "decision": "ALLOW",
  "risk_flags": ["ip_reputation"],
  "components": {
    "S_identity": 44.64,
    "S_history": 88.0,
    "S_context": 95.0,
    "R_risk": 6.0,
    "confidence": 0.93
  }
}
```

| Field | Type | Range | Notes |
|---|---|---|---|
| `trust_score` | float | `[0,100]` | Final clamped TS |
| `decision` | enum | `ALLOW`\|`STEP_UP`\|`DENY` | Per policy thresholds |
| `risk_flags` | string[] | — | Names of triggered rules, `trust_engine/rules.py` |
| `components.*` | float | — | Debug/audit breakdown, not required by minimal clients |
