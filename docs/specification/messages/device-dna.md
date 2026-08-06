# Device DNA — Data Structure

See RFC-0001 §10 (Privacy Addendum, normative) and
`reference/entropy-engine/normalizer.py`.

**Wire representation is a hash only:**

```json
{ "device_dna_hash": "hex(32 bytes)" }
```

**Server-side allow-listed input fields** (never transmitted raw beyond
the client that already possesses them):

| Field | Example | Note |
|---|---|---|
| `platform` | `"Linux"` | Coarse OS family only |
| `screen_class` | `"1920x1080"` | Bucketed resolution class |
| `timezone_offset_min` | `120` | |
| `language` | `"ro"` | |
| `color_depth_class` | `"24bit"` | Bucketed |
| `hardware_concurrency_class` | `"4-8"` | Bucketed CPU core count |
| `gpu_vendor_class` | `"intel"` | Vendor only, never full renderer string |

Any field not in this list is dropped before hashing
(`normalizer.py::_ALLOWED_DEVICE_FIELDS`), fail-closed by design.
