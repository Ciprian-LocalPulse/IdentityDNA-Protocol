# Changelog

## Unreleased

### Fixed
- **`S_identity` formula scaling bug** (`docs/mathematics/formal-model.md`
  §3.2). The original formula `100·(1-d)/2·confidence` has a maximum
  value of `50·confidence` at `d=0` (a *perfect* device/behavior match) —
  meaning a fully-recognized returning device scored no differently from
  an unknown first-time device using the "neutral prior" default. This
  made trust score effectively unable to improve from device recognition
  alone. Corrected to `100·(1-d/2)·confidence`, which ranges the full
  `[0, 100·confidence]` and treats `d=1` (orthogonal / no information) as
  the neutral midpoint. The "no baseline yet" case is now explicitly
  defined as `d=1` (§3.2.1) rather than an ad hoc separate constant.
  Discovered via `reference/storage/` persistence testing: trust score
  was not increasing across repeated legitimate sessions for the same
  subject as expected. See `tests/unit/test_trust_engine.py`.

### Added
- `reference/storage/sqlite_store.py` — SQLite-backed persistence for
  subject baselines and trust history, so state survives process
  restarts (Phase 1 was in-memory only).
- `PersistentSubjectRegistry` / `PersistentTrustHistory` — drop-in
  persistent variants of the in-memory reference classes.
- `identitydna reset` CLI command to wipe persisted demo state.
- Gateway bootstrap rule: a subject's first-ever Identity Vector is now
  enrolled as their baseline regardless of that session's trust decision
  (previously, enrollment on `DENY` was skipped entirely, which made a
  low-scoring first session an unrecoverable dead end — no baseline
  could ever form, so distance stayed `None`/neutral forever).
- **History deadlock** (`formal-model.md` §3.3.1). With the strict
  original reading of "accepted without step-up", `STEP_UP` counted as a
  history *failure*, but `ALLOW` requires decent `S_history` — so a
  subject could never accumulate the history needed to ever reach
  `ALLOW`, a permanent-lockout deadlock discovered by running the demo
  handshake repeatedly against the new SQLite persistence layer.
  Redefined `match(t-k)=1` for `decision ∈ {ALLOW, STEP_UP}` (only an
  outright `DENY` counts as failure), and first-ever (no-baseline)
  sessions are no longer recorded into history at all. Verified end to
  end: repeated logins from the same device now progress
  `DENY → STEP_UP → STEP_UP (higher score, plateaus)` instead of being
  stuck at `DENY` forever. See
  `tests/unit/test_handshake_integration.py::test_trust_score_improves_across_repeated_sessions_same_device`.

## Phase 1.2 — Property-based / fuzz testing

### Added
- `tests/property/` — Hypothesis-driven property-based tests across
  crypto (14 tests), identity-engine (5), trust-engine (10), session-engine
  (7), and adversarial handshake state-machine tests (9): 45 property
  tests, each running 100-300+ randomized examples per run (thousands of
  cases total per full suite run), on top of the 30 example-based unit
  tests. Full suite: 75 tests.

### Fixed
- **Remote DoS via malformed `ENTROPY.behavioral_sample`**
  (`entropy-engine/normalizer.py::normalize_behavior`). A client sending
  `typing_cadence_ms` as a non-list value (e.g. a string) caused an
  unhandled `TypeError` inside `sum()`/iteration, which would crash the
  request handler on the server side — an unauthenticated remote DoS
  vector, since ENTROPY is processed before any signature is verified.
  Found by `tests/property/test_identity_properties.py`'s fuzz strategy
  (which deliberately includes wrong-typed values for every field).
  Fixed to validate/coerce defensively and degrade to the neutral case
  instead of raising, per threat-model.md §2 ("the client device is
  fully untrusted"). Same defensive fix applied to
  `normalize_context`'s `tz_offset_min` parsing (same bug class, found
  by inspection after the first fix).
- `TrustHistory.score()` floating-point drift slightly outside `[0,100]`
  (e.g. `100.00000000000001`) under certain EWMA summation orders — now
  defensively clamped. Found by
  `tests/property/test_trust_properties.py::test_history_all_true_gives_max_score`.

Install: `pip install hypothesis` (added to `reference/requirements.txt`).
Run: `python3 -m pytest tests/property -v`
