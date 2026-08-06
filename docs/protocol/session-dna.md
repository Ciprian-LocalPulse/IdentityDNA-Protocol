# Session DNA

Session DNA is a unique, ephemeral cryptographic identity generated for a specific session. It is valid only for a short window and only for the session it was created for — it cannot be replayed or reused elsewhere.

## Properties
- **Unique per session** — no two sessions share a Session DNA.
- **Ephemeral** — valid for a limited time window.
- **Non-transferable** — not valid outside the session or context it was issued for.

## Generation
Session DNA is produced by the Cryptographic Core using the current Identity Stream state and session-specific parameters. See `docs/mathematics/proof.md` (in progress) for the intended formal security properties.

## Status
Draft — exact cryptographic construction to be finalized and reviewed as part of Roadmap Phase 1 and Phase 8 (independent security audit).
