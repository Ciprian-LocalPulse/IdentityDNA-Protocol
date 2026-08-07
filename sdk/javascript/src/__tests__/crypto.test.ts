import { test } from "node:test";
import assert from "node:assert/strict";
import { hashBlake3Str, hkdf, csprngBytes } from "../crypto/primitives.js";
import { SigningKeyPair, verifySignature } from "../crypto/signatures.js";
import { EphemeralKeyPair } from "../crypto/keyAgreement.js";

test("hash is deterministic", () => {
  const a = hashBlake3Str(["x"], "D");
  const b = hashBlake3Str(["x"], "D");
  assert.deepEqual(a, b);
});

test("hash domain separation changes output", () => {
  const a = hashBlake3Str(["same"], "DOMAIN-A");
  const b = hashBlake3Str(["same"], "DOMAIN-B");
  assert.notDeepEqual(a, b);
});

test("hash requires non-empty domain", () => {
  assert.throws(() => hashBlake3Str(["x"], ""));
});

test("hkdf output length matches request", () => {
  const out = hkdf(Buffer.from("ikm"), Buffer.from("salt"), "info", 48);
  assert.equal(out.length, 48);
});

test("ed25519 signature roundtrip", () => {
  const kp = SigningKeyPair.generate();
  const msg = new TextEncoder().encode("transcript-hash-placeholder");
  const sig = kp.sign(msg);
  assert.ok(verifySignature(kp.publicKeyB64, msg, sig));
});

test("ed25519 rejects tampered message", () => {
  const kp = SigningKeyPair.generate();
  const sig = kp.sign(new TextEncoder().encode("original"));
  assert.ok(!verifySignature(kp.publicKeyB64, new TextEncoder().encode("tampered"), sig));
});

test("ed25519 rejects wrong key", () => {
  const a = SigningKeyPair.generate();
  const b = SigningKeyPair.generate();
  const msg = new TextEncoder().encode("msg");
  const sig = a.sign(msg);
  assert.ok(!verifySignature(b.publicKeyB64, msg, sig));
});

test("x25519 ecdh is symmetric", () => {
  const a = EphemeralKeyPair.generate();
  const b = EphemeralKeyPair.generate();
  const secretAB = a.ecdh(b.publicKeyB64);
  const secretBA = b.ecdh(a.publicKeyB64);
  assert.deepEqual(secretAB, secretBA);
});

test("csprng produces correct length and no obvious repeats", () => {
  const a = csprngBytes(32);
  const b = csprngBytes(32);
  assert.equal(a.length, 32);
  assert.notDeepEqual(a, b);
});
