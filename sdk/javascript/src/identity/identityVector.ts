/**
 * Identity Engine — Identity Vector construction (TypeScript SDK).
 * Mirrors reference/identity-engine/identity_vector.py exactly.
 * See formal-model.md §2, RFC-0001 §7.
 */
import { randomUUID } from "node:crypto";
import {
  normalizeDevice,
  normalizeBehavior,
  normalizeContext,
  digestToVector,
  VECTOR_DIM,
  type DeviceRaw,
  type BehaviorRaw,
  type ContextRaw,
} from "../entropy/normalizer.js";
import { hashBlake3 } from "../crypto/primitives.js";

export interface IdentityWeights {
  device: number;
  behavior: number;
  context: number;
}

// formal-model.md §2.2 default weights
export const DEFAULT_WEIGHTS: IdentityWeights = { device: 0.5, behavior: 0.3, context: 0.2 };

export class DegenerateInputError extends Error {}

export class IdentityVector {
  constructor(
    public readonly identityVectorId: string,
    public readonly vector: number[],
    public readonly ivDigest: string
  ) {}

  /** Both vectors are unit-norm (formal-model.md §2.3), so cosine
   * similarity reduces to the dot product. */
  cosineSimilarity(other: IdentityVector): number {
    let sum = 0;
    for (let i = 0; i < this.vector.length; i++) sum += this.vector[i] * other.vector[i];
    return sum;
  }

  /** formal-model.md §2.4 */
  distance(other: IdentityVector): number {
    return 1.0 - this.cosineSimilarity(other);
  }
}

function weightedSum(vd: number[], vb: number[], vc: number[], w: IdentityWeights): number[] {
  const out = new Array<number>(vd.length);
  for (let i = 0; i < vd.length; i++) {
    out[i] = vd[i] * w.device + vb[i] * w.behavior + vc[i] * w.context;
  }
  return out;
}

function l2Normalize(v: number[]): number[] {
  let normSq = 0;
  for (const x of v) normSq += x * x;
  const norm = Math.sqrt(normSq);
  if (norm === 0) {
    throw new DegenerateInputError(
      "Identity vector has zero norm (RFC-0001 §7): reject as ERR_MALFORMED"
    );
  }
  return v.map((x) => x / norm);
}

function toBytesBE(x: number): Uint8Array {
  // mirrors Python's int(x * 1e9).to_bytes(8, "big", signed=True)
  const scaled = BigInt(Math.trunc(x * 1e9));
  const buf = new ArrayBuffer(8);
  new DataView(buf).setBigInt64(0, scaled, false);
  return new Uint8Array(buf);
}

function concatAll(arrays: Uint8Array[]): Uint8Array {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

export function compileIdentityVector(
  deviceRaw: DeviceRaw,
  behaviorRaw: BehaviorRaw,
  contextRaw: ContextRaw,
  rpSalt: string,
  weights: IdentityWeights = DEFAULT_WEIGHTS,
  dim: number = VECTOR_DIM
): IdentityVector {
  const sum = weights.device + weights.behavior + weights.context;
  if (Math.abs(sum - 1.0) > 1e-9) {
    throw new Error("weights must sum to 1 (formal-model.md §2.2)");
  }

  const deviceDigest = normalizeDevice(deviceRaw, rpSalt);
  const behaviorDigest = normalizeBehavior(behaviorRaw);
  const contextDigest = normalizeContext(contextRaw);

  const vd = digestToVector(deviceDigest, dim);
  const vb = digestToVector(behaviorDigest, dim);
  const vc = digestToVector(contextDigest, dim);

  const raw = weightedSum(vd, vb, vc, weights);
  const normalized = l2Normalize(raw);

  // Python: hash_blake3(b"".join(chunk for chunk in normalized), domain=...)
  // -- ONE concatenated blob as a single part, NOT 256 separately
  // length-prefixed parts. Must match exactly for cross-language
  // iv_digest parity.
  const concatenated = concatAll(normalized.map(toBytesBE));
  const ivDigestBytes = hashBlake3([concatenated], "IDP-IV-DIGEST-v1");
  const ivDigest = Buffer.from(ivDigestBytes).toString("hex");

  return new IdentityVector(randomUUID(), normalized, ivDigest);
}
