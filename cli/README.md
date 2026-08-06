# IdentityDNA Protocol CLI

Status: **Implemented (Phase 1)**.

## Install / Run

```bash
cd cli
pip install click --break-system-packages   # if not already installed via reference/requirements.txt
python3 -m identitydna --help
```

## Commands

| Command | Description |
|---|---|
| `identitydna login` | Run a complete local demo handshake (client + server in-process) |
| `identitydna compile <file.json>` | Compile an Identity Vector from `{"device":..,"behavior":..,"context":..,"rp_salt":..}` |
| `identitydna trust <file.json>` | Run the Trust Engine against an arbitrary context |
| `identitydna generate` | Generate a fresh Ed25519 + X25519 demo keypair |
| `identitydna inspect <envelope.json>` | Validate a message envelope against the RFC-0001 §4 schema |
| `identitydna session` | Demonstrate Session DNA generation, rotation, and expiration checks |
| `identitydna benchmark [--iterations N]` | Micro-benchmark hashing / HKDF / signing throughput |
| `identitydna verify` | *(planned, ROADMAP.md Phase 2 — verify an externally-supplied handshake transcript)* |

Tracked in `../ROADMAP.md`.
