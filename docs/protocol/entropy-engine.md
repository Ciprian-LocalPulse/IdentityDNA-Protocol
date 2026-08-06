# Entropy Engine

Transforms raw entropy collected from multiple sources into deterministic identity vectors usable by the Identity Stream.

## Candidate Entropy Sources
- Device-level signals (hardware/OS characteristics, sensor data where available).
- Behavioral signals (typing cadence, interaction patterns).
- Contextual signals (network characteristics, geolocation where consented and appropriate).
- Environmental signals (time-based and session-based factors).

## Design Considerations
- Entropy source quality directly affects the strength of the resulting identity vector (see `SECURITY.md`).
- Sources must be chosen carefully to avoid excessive or unnecessary collection of personal data (see `ETHICS.md`, Privacy by Design).
- Some sources may not be available or reliable across all platforms (e.g., constrained IoT devices vs. modern browsers).

## Status
Draft — exact derivation and normalization functions are being formalized in `docs/mathematics/entropy.md`.
