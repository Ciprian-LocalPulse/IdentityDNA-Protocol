/**
 * Entropy Engine — normalization layer (TypeScript SDK).
 *
 * Mirrors reference/entropy-engine/normalizer.py exactly: same allow-list,
 * same domain-separation tags, same defensive/fail-closed handling of
 * malformed input (RFC-0001 §10; see CHANGELOG.md for the DoS bug this
 * defensive handling was added to fix on the Python side — replicated
 * here proactively rather than waiting to rediscover it).
 */
import { hashBlake3Str, hkdfExpandVector } from "../crypto/primitives.js";

export const VECTOR_DIM = 256;

/** Fields explicitly allowed for Device DNA collection (RFC-0001 §10.1/10.3).
 * MUST match the Python allow-list exactly, field-for-field. */
const ALLOWED_DEVICE_FIELDS = [
  "platform",
  "screen_class",
  "timezone_offset_min",
  "language",
  "color_depth_class",
  "hardware_concurrency_class",
  "gpu_vendor_class",
] as const;

export type DeviceRaw = Partial<Record<(typeof ALLOWED_DEVICE_FIELDS)[number], unknown>>;
export interface BehaviorRaw {
  typing_cadence_ms?: unknown;
  pointer_entropy?: unknown;
}
export interface ContextRaw {
  tz_offset_min?: unknown;
  locale?: unknown;
}

/** `rpSalt` is a per-Relying-Party salt (RFC-0001 §10.4) preventing
 * cross-RP linkage of the same physical device by a compromised operator. */
export function normalizeDevice(raw: DeviceRaw, rpSalt: string): Uint8Array {
  const sorted = [...ALLOWED_DEVICE_FIELDS].sort();
  const filtered = sorted.map((k) => `${k}=${String(raw[k] ?? "unknown")}`);
  const canonical = filtered.join("|");
  return hashBlake3Str([canonical, rpSalt], "IDP-DEVICE-DNA-v1");
}

function isFiniteNumber(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** Defensive/fail-closed: client-supplied input is untrusted
 * (threat-model.md §2). Malformed typing_cadence_ms degrades to the
 * neutral/empty case instead of throwing. */
export function normalizeBehavior(raw: BehaviorRaw): Uint8Array {
  const cadenceRaw = raw.typing_cadence_ms;
  const cadence = Array.isArray(cadenceRaw) ? cadenceRaw.filter(isFiniteNumber) : [];

  let pointerEntropy = 0.0;
  if (isFiniteNumber(raw.pointer_entropy)) {
    pointerEntropy = raw.pointer_entropy;
  } else if (typeof raw.pointer_entropy === "string" && raw.pointer_entropy.trim() !== "") {
    const parsed = Number(raw.pointer_entropy);
    pointerEntropy = Number.isFinite(parsed) ? parsed : 0.0;
  }

  let mean = 0.0;
  let stddev = 0.0;
  if (cadence.length > 0) {
    mean = cadence.reduce((a, b) => a + b, 0) / cadence.length;
    const variance = cadence.reduce((a, b) => a + (b - mean) ** 2, 0) / cadence.length;
    stddev = Math.sqrt(variance);
  }

  const summary = `mean=${mean.toFixed(2)}|std=${stddev.toFixed(2)}|ptr=${pointerEntropy.toFixed(4)}`;
  return hashBlake3Str([summary], "IDP-BEHAVIOR-v1");
}

export function normalizeContext(raw: ContextRaw): Uint8Array {
  let tz = 0;
  if (isFiniteNumber(raw.tz_offset_min)) {
    tz = Math.trunc(raw.tz_offset_min);
  } else if (typeof raw.tz_offset_min === "string") {
    const parsed = parseInt(raw.tz_offset_min, 10);
    tz = Number.isFinite(parsed) ? parsed : 0;
  }
  const locale = raw.locale === undefined || raw.locale === null ? "unknown" : String(raw.locale);
  const summary = `tz=${tz}|locale=${locale}`;
  return hashBlake3Str([summary], "IDP-CONTEXT-v1");
}

export function digestToVector(digest: Uint8Array, n: number = VECTOR_DIM): number[] {
  return hkdfExpandVector(digest, n);
}
