# IdentityDNA Protocol — Formal Mathematical Model

Companion to RFC-0001 §7–9. This document is the single source of truth for
the numeric definitions; `reference/*-engine/*.py` MUST implement exactly
these formulas (see cross-references to source files).

---

## 1. Notation

- `H(·)` — BLAKE3-256, output interpreted as a big-endian integer or byte
  string depending on context.
- `||` — byte concatenation.
- `R^n` — real vector space of dimension `n` (default `n = 256`).
- `clamp(x, a, b) = max(a, min(b, x))`
- `t` — discrete time index (one per `VERIFY` round).

---

## 2. Identity Vector

### 2.1 Layer functions

Each layer function maps raw, consented input to a fixed-length digest,
then to a vector in `[0,1]^n` via a keyed stream expansion:

```
f_device(D)   = Expand( H("IDP-DEVICE-DNA-v1"   || normalize_device(D)),   n )
f_behavior(B) = Expand( H("IDP-BEHAVIOR-v1"     || normalize_behavior(B)), n )
f_context(C)  = Expand( H("IDP-CONTEXT-v1"      || normalize_context(C)),  n )
```

`Expand(seed, n)` is HKDF-Expand-style: it produces `n` bytes from a 32-byte
seed, each byte mapped to `[0,1]` by dividing by 255.

`normalize_device`, `normalize_behavior`, `normalize_context` are
versioned, documented transforms (implemented in
`reference/entropy-engine/normalizer.py`) that MUST be idempotent and MUST
discard any field not explicitly listed in the Device DNA disclosure
(RFC-0001 §10).

### 2.2 Combinator

```
IV_raw = f_device(D) ⊙ w_d  +  f_behavior(B) ⊙ w_b  +  f_context(C) ⊙ w_c
```

where `⊙` is element-wise (Hadamard) product with a scalar broadcast, and
`w_d + w_b + w_c = 1`, default `(w_d, w_b, w_c) = (0.5, 0.3, 0.2)` — device
signals are weighted most heavily because they are the most stable
identity-correlated layer; behavior and context contribute corroborating,
lower-weight signal.

### 2.3 Normalization onto the unit hypersphere

```
IV = IV_raw / ||IV_raw||_2      (L2 normalization; ||IV_raw||_2 != 0 required)
```

If `||IV_raw||_2 = 0` (degenerate all-zero input) the implementation MUST
reject with `ERR_MALFORMED` rather than divide by zero.

### 2.4 Identity Distance

For two Identity Vectors `IV_a, IV_b` from the same claimed identity across
sessions:

```
d(IV_a, IV_b) = 1 - cos_sim(IV_a, IV_b) = 1 - (IV_a · IV_b)
```

(cosine similarity simplifies to the dot product since both vectors are
unit-norm). `d ∈ [0, 2]`. Small `d` across sessions increases `S_history`
(§3.2); large `d` is a risk signal (§3.4).

---

## 3. Trust Function

### 3.1 Overall definition

```
TS(t) = clamp( w1·S_identity(t) + w2·S_history(t) + w3·S_context(t) - w4·R_risk(t),  0, 100 )
```

Default weights (policy-overridable, see `trust_engine/weights.py`):
`w1 = 0.35, w2 = 0.30, w3 = 0.15, w4 = 0.20` (risk is subtracted, not
averaged in, so a single severe risk flag can dominate the score).

### 3.2 Identity Consistency Score

```
S_identity(t) = 100 · (1 - d(IV(t), IV_baseline)/2) · confidence(t)
```

`IV_baseline` is the enrolled/reference Identity Vector for the claimed
principal; `confidence(t)` is defined in §5. Since `d ∈ [0, 2]`
(§2.4), this formula ranges over `[0, 100·confidence]`: a perfect match
(`d = 0`) scores the maximum `100·confidence`; a neutral/uninformative
comparison (`d = 1`, i.e. orthogonal vectors — including the "no
baseline enrolled yet" case, which is treated as `d = 1` by convention,
see §3.2.1) scores the midpoint `50·confidence`; a maximally divergent
comparison (`d = 2`) scores `0`. This scaling is deliberate: it ensures
a genuinely recognized device is scored strictly higher than an unknown
one, rather than both capping at the same value (an earlier draft of
this formula divided by 2 without an offset, which collapsed the
"perfect match" and "no information" cases to an identical score — see
CHANGELOG.md for the correction).

#### 3.2.1 No-Baseline Convention

When no baseline exists yet for a subject (first-ever session), callers
MUST pass `d = 1` (the neutral midpoint) to `S_identity`, not `d = 0`
and not treat it as automatically maximal or minimal trust. A first
session is genuinely uninformative about identity consistency — it is
neither evidence of a match nor of a mismatch.

### 3.3 History Score (exponentially-weighted)

```
S_history(t) = 100 · Σ_{k=1}^{K} λ^(k-1) · match(t-k)  /  Σ_{k=1}^{K} λ^(k-1)
```

`match(t-k) ∈ {0,1}`, `λ ∈ (0,1)` default `0.85` is the recency decay,
`K` is a configurable history window (default 20 sessions).

#### 3.3.1 Definition of `match(t-k)`

`match(t-k) = 1` if session `t-k` reached `decision ∈ {ALLOW, STEP_UP}`
(i.e. was not outright rejected), `0` if it reached `DENY`.

This intentionally includes `STEP_UP` as a positive history signal, not
only `ALLOW`. Rationale: `STEP_UP` means the protocol asked for
additional out-of-band verification (e.g. an OTP/MFA challenge) that is
outside the scope of RFC-0001's wire messages — this reference model
does not simulate that challenge failing. Treating every `STEP_UP` as a
history *failure* creates a structural deadlock: `ALLOW` requires a
reasonable `S_history`, but `S_history` could only ever improve via
`ALLOW`, and a first-ever (no-baseline) session can score no higher than
`STEP_UP` at best (§3.2.1) — so a subject could never accumulate the
history needed to ever reach `ALLOW`. A production deployment that does
model step-up completion/failure as an explicit event SHOULD instead
record `match(t-k) = 1` only when the step-up challenge is completed
successfully, and `0` if it is abandoned or failed — this reference
implementation approximates that as "assume step-up succeeds" absent an
actual step-up subsystem. See `CHANGELOG.md` for the discovery context.

A session's **first-ever** occurrence for a subject (no baseline
enrolled yet, §3.2.1) MUST NOT be recorded into history at all — it is
not yet a meaningful judgment of the subject's identity consistency, and
recording it as a failure would itself reintroduce the deadlock above.

### 3.4 Risk Function

```
R_risk(t) = Σ_i severity_i · indicator_i(t)
```

`indicator_i(t) ∈ {0,1}` for each registered risk rule in
`trust_engine/rules.py` (impossible travel, IP reputation, known-bad
device hash, replay attempt, excessive velocity, TOR/proxy exit node,
Device DNA drift `d > threshold`, behavioral anomaly). `severity_i` is a
policy-configured weight per rule, default range `[5, 40]`.

### 3.5 Context Score

```
S_context(t) = 100 · Π_j p_j(t)
```

where each `p_j(t) ∈ [0,1]` is a prior derived from a contextual factor
(time-of-day-typical-for-user, geolocation-typical-for-user, known
network). The product form means any single strongly-atypical context
factor pulls the whole context score toward zero (conjunctive, not
additive — one glaring anomaly should not be diluted by several
unremarkable ones).

### 3.6 Decision Mapping

See RFC-0001 §8; `decision = ALLOW | STEP_UP | DENY` from threshold
comparison against `TS(t)`.

---

## 4. Session Evolution

Session DNA rotation (RFC-0001 §9) can be viewed as a Markov chain over
key material:

```
SDNA_(k+1) = HKDF( SDNA_k, rotation_nonce_k, "IDP-ROTATE-v1", 32 )
```

Because HKDF is a one-way function, knowledge of `SDNA_(k+1)` does not
reveal `SDNA_k` (backward secrecy across rotations), and compromise of
`SDNA_k` does not reveal `SDNA_(k-1)` (forward secrecy is inherited from
the initial ephemeral ECDH per RFC-0001 §9).

Expected session lifetime under continuous `ALLOW` decisions:

```
E[lifetime] = Σ_{k=0}^{∞} rotation_interval_s · P(TS(t_k) >= step_up_threshold for all t_0..t_k)
```

which decays geometrically if each round's step-up probability `p` is
treated as i.i.d.: `E[lifetime] ≈ rotation_interval_s / (1 - p)`.

---

## 5. Confidence Function

```
confidence(t) = 1 - exp( -n_eff(t) / τ )
```

`n_eff(t)` is the effective number of independent corroborating signals
available at time `t` (device + behavioral + contextual layers that
successfully produced non-degenerate input), `τ` (default `2.0`) is a
saturation constant. `confidence → 1` as more independent signal layers
are present; a session with only one working layer (e.g. behavioral
signals unavailable) has its `S_identity` contribution damped
accordingly rather than trusted at full weight from partial evidence.

---

## 6. Entropy Function

Used to size Device DNA hash space and reason about collision risk:

```
H_shannon(X) = - Σ_x P(x) · log2 P(x)
```

For a Device DNA hash of `b` bits, the birthday-bound collision
probability across `N` distinct devices is approximately:

```
P_collision ≈ 1 - exp( -N(N-1) / 2^(b+1) )
```

With `b = 256` (BLAKE3-256 output), `N` would need to approach `2^128`
before collision probability becomes non-negligible — i.e., collision is
not a practical concern for the hash itself; the practical risk is
low-entropy *input* (few actually-observable device configurations),
which is why Device DNA is a corroborating signal (`w_d = 0.5` of the
Identity Vector) and never a sole authentication factor.

---

## 7. Worked Numeric Example

Given `d(IV(t), IV_baseline) = 0.04` (very similar), `confidence(t) = 0.93`,
`S_history(t) = 88`, `S_context(t) = 95`, `R_risk(t) = 6` (minor,
e.g. new-but-plausible IP range):

```
S_identity = 100 * (1 - 0.04/2) * 0.93 = 100 * 0.98 * 0.93 = 91.14
TS = 0.35*91.14 + 0.30*88 + 0.15*95 - 0.20*6
   = 31.90 + 26.4 + 14.25 - 1.2
   = 71.35  →  STEP_UP  (between default thresholds 50 and 80)
```

This matches the reference implementation's output for the equivalent
fixture in `tests/unit/test_trust_engine.py::test_worked_example`.

### 7.1 No-Baseline Example (First Session)

For comparison, a first-ever session for the same subject (no baseline,
`d = 1` by convention, §3.2.1), everything else equal:

```
S_identity = 100 * (1 - 1/2) * 0.93 = 46.5
TS = 0.35*46.5 + 0.30*50 + 0.15*95 - 0.20*0
   = 16.28 + 15 + 14.25 - 0
   = 45.53  →  DENY (below step_up_threshold 50; history also starts neutral at 50)
```

A subsequent session from the *same, now-recognized* device (§7, `d =
0.04`) scores nearly double the identity component (91.14 vs 46.5) —
this is the mechanism by which repeated legitimate use is meant to
raise trust over time, distinct from (and additive to) the separate
history-based improvement in §3.3.

