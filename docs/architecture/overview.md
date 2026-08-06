# Architecture Overview

IdentityDNA Protocol is composed of six cooperating engines, split across client and server responsibilities.

## Components

| Engine | Side | Responsibility |
|---|---|---|
| Identity Engine | Client | Collects and normalizes entropy from multiple layers. |
| Entropy Engine | Client | Transforms raw entropy into deterministic identity vectors. |
| Trust Engine | Server | Continuously analyzes behavior, context, and environment to score risk. |
| Cryptographic Core | Client/Server | Generates and validates Session DNA. |
| Verification Engine | Server | Verifies identity streams in real time under zero-trust principles. |
| Session Engine | Server | Manages the lifecycle of the Session DNA. |

## Data Flow

```
Client                                   Server
------                                   ------
Identity Engine  ---collects--->  (device/behavior/context/env)
      |
      v
Entropy Engine  ---derives--->  Identity Vector
      |
      v
Identity Stream  ------------------------>  Verification Engine
                                                   |
                                                   v
                                            Trust Engine (score)
                                                   |
                                                   v
                                          Session Engine (Session DNA)
                                                   |
                                                   v
                                         Access Decision (grant/deny/step-up)
```

See `client.md`, `server.md`, `sdk.md`, and `api.md` for component-level detail.
