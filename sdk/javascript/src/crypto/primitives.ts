/**
 * IdentityDNA Protocol — Cryptographic Core (TypeScript SDK)
 *
 * Mirrors reference/crypto/primitives.py exactly: same domain-separation
 * scheme (RFC-0001 §11.3), same HKDF construction, same canonical JSON
 * rules (RFC-0001 §11.2). This is what makes the TS client interoperable
 * with the Python reference server — a transcript hash computed here
 * must equal the one computed server-side for the same wire messages.
 */
import { blake3 } from "@noble/hashes/blake3.js";
import { sha3_256 } from "@noble/hashes/sha3.js";
import { hkdf as nobleHkdf, expand as hkdfExpand } from "@noble/hashes/hkdf.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { randomBytes } from "@noble/hashes/utils.js";

const textEncoder = new TextEncoder();

/** RFC-0001 §11.1: RNG MUST be a CSPRNG. */
export function csprngBytes(n: number): Uint8Array {
  if (n <= 0) throw new Error("n must be positive");
  return randomBytes(n);
}

function u32be(n: number): Uint8Array {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, n, false);
  return b;
}

function u16be(n: number): Uint8Array {
  const b = new Uint8Array(2);
  new DataView(b.buffer).setUint16(0, n, false);
  return b;
}

function concatBytes(...arrays: Uint8Array[]): Uint8Array {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

/**
 * Domain-separated BLAKE3-256 (falls back conceptually to SHA3-256 in the
 * Python reference if blake3 is unavailable; this SDK always has blake3
 * available via @noble/hashes, so no fallback branch is needed here).
 * RFC-0001 §11.3. MUST byte-for-byte match primitives.py::hash_blake3
 * for the same (parts, domain).
 */
export function hashBlake3(parts: Uint8Array[], domain: string): Uint8Array {
  if (!domain) throw new Error("domain separation tag is required (RFC-0001 §11.3)");
  const domainBytes = textEncoder.encode(domain);
  const prefix = concatBytes(u16be(domainBytes.length), domainBytes);
  const payloadParts = [prefix];
  for (const p of parts) {
    payloadParts.push(u32be(p.length), p);
  }
  return blake3(concatBytes(...payloadParts));
}

/** Convenience overload accepting strings, auto-encoded as UTF-8. */
export function hashBlake3Str(parts: (Uint8Array | string)[], domain: string): Uint8Array {
  const bytesParts = parts.map((p) => (typeof p === "string" ? textEncoder.encode(p) : p));
  return hashBlake3(bytesParts, domain);
}

/** HKDF-SHA256 (RFC 5869). Used for Session DNA derivation (RFC-0001 §9). */
export function hkdf(ikm: Uint8Array, salt: Uint8Array | undefined, info: string, length = 32): Uint8Array {
  return nobleHkdf(sha256, ikm, salt, textEncoder.encode(info), length);
}

/** Expand a 32-byte seed into `n` floats in [0,1] via HKDF-Expand ONLY
 * (no extract step -- `seed` is treated directly as the PRK, matching
 * Python's `cryptography.hazmat.primitives.kdf.hkdf.HKDFExpand`, NOT
 * the full extract-then-expand `hkdf()` above). Used by the Identity
 * Engine layer functions (formal-model.md §2.1). Using full HKDF here
 * instead of expand-only would silently produce a different Identity
 * Vector than the Python reference for the same input -- this was
 * caught via the interop fixture check in tests/interop/. */
export function hkdfExpandVector(seed: Uint8Array, n: number): number[] {
  const raw = hkdfExpand(sha256, seed, textEncoder.encode("IDP-VECTOR-EXPAND-v1"), n);
  return Array.from(raw, (b) => b / 255.0);
}

/**
 * RFC 8785-style canonicalization (sorted keys, compact separators, no
 * insignificant whitespace). Used to build the transcript hash input
 * (RFC-0001 §11.2). MUST match primitives.py::canonical_json's output
 * byte-for-byte for the same logical object, since both sides feed this
 * into the same transcript hash.
 */
export function canonicalJson(obj: unknown): Uint8Array {
  return textEncoder.encode(canonicalize(obj));
}

function canonicalize(obj: unknown): string {
  if (obj === null || obj === undefined) return "null";
  if (typeof obj === "number" || typeof obj === "boolean") return JSON.stringify(obj);
  if (typeof obj === "string") return JSON.stringify(obj);
  if (Array.isArray(obj)) return "[" + obj.map(canonicalize).join(",") + "]";
  if (typeof obj === "object") {
    const keys = Object.keys(obj as Record<string, unknown>).sort();
    const entries = keys.map(
      (k) => JSON.stringify(k) + ":" + canonicalize((obj as Record<string, unknown>)[k])
    );
    return "{" + entries.join(",") + "}";
  }
  throw new Error(`cannot canonicalize value of type ${typeof obj}`);
}

export { sha3_256 };
