import { test } from "node:test";
import assert from "node:assert/strict";
import { compileIdentityVector, DegenerateInputError } from "../identity/identityVector.js";

const DEVICE = {
  platform: "Linux", screen_class: "1920x1080", timezone_offset_min: 120,
  language: "ro", color_depth_class: "24bit", hardware_concurrency_class: "4-8",
  gpu_vendor_class: "intel",
};
const BEHAVIOR = { typing_cadence_ms: [120, 110, 130, 125], pointer_entropy: 0.42 };
const CONTEXT = { tz_offset_min: 120, locale: "ro-RO" };

test("identity vector is unit norm", () => {
  const iv = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a");
  const normSq = iv.vector.reduce((s, x) => s + x * x, 0);
  assert.ok(Math.abs(normSq - 1.0) < 1e-9);
});

test("identity vector is deterministic", () => {
  const iv1 = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a");
  const iv2 = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a");
  assert.deepEqual(iv1.vector, iv2.vector);
  assert.equal(iv1.ivDigest, iv2.ivDigest);
});

test("different salt changes the vector", () => {
  const iv1 = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a");
  const iv2 = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-b");
  assert.notDeepEqual(iv1.vector, iv2.vector);
});

test("self distance is zero", () => {
  const iv = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a");
  assert.ok(Math.abs(iv.distance(iv)) < 1e-9);
});

test("different device increases distance", () => {
  const iv1 = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a");
  const iv2 = compileIdentityVector({ ...DEVICE, platform: "Windows", gpu_vendor_class: "nvidia" }, BEHAVIOR, CONTEXT, "salt-a");
  assert.ok(iv1.distance(iv2) > 0.01);
});

test("weights must sum to one", () => {
  assert.throws(() =>
    compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, "salt-a", { device: 0.9, behavior: 0.9, context: 0.2 })
  );
});

test("malformed typing_cadence_ms does not crash (fail-closed)", () => {
  const malformedBehavior = { typing_cadence_ms: "0" as unknown, pointer_entropy: 0.5 };
  const iv = compileIdentityVector(DEVICE, malformedBehavior, CONTEXT, "salt-a");
  assert.equal(iv.vector.length, 256);
});

test("malformed context tz does not crash (fail-closed)", () => {
  const malformedContext = { tz_offset_min: "not-a-number" as unknown, locale: "ro-RO" };
  const iv = compileIdentityVector(DEVICE, BEHAVIOR, malformedContext, "salt-a");
  assert.equal(iv.vector.length, 256);
});
