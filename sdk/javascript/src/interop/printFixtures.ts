/**
 * Prints deterministic outputs for a fixed set of inputs, in a format
 * a Python script can parse and diff against. Used only for the
 * cross-language interop check in tests/interop/ -- not part of the
 * published SDK surface.
 */
import { hashBlake3Str, hkdf } from "../crypto/primitives.js";
import { normalizeDevice, normalizeBehavior, normalizeContext } from "../entropy/normalizer.js";
import { compileIdentityVector } from "../identity/identityVector.js";

const DEVICE = {
  platform: "Linux", screen_class: "1920x1080", timezone_offset_min: 120,
  language: "ro", color_depth_class: "24bit", hardware_concurrency_class: "4-8",
  gpu_vendor_class: "intel",
};
const BEHAVIOR = { typing_cadence_ms: [120, 110, 130, 125], pointer_entropy: 0.42 };
const CONTEXT = { tz_offset_min: 120, locale: "ro-RO" };
const RP_SALT = "demo-rp-salt-v1";

const out: Record<string, string> = {};

out["hash_domain_a"] = Buffer.from(hashBlake3Str(["same-input"], "DOMAIN-A")).toString("hex");
out["hash_domain_b"] = Buffer.from(hashBlake3Str(["same-input"], "DOMAIN-B")).toString("hex");

out["hkdf_basic"] = Buffer.from(hkdf(Buffer.from("ikm-material"), Buffer.from("salt"), "test", 48)).toString("hex");

out["device_hash"] = Buffer.from(normalizeDevice(DEVICE, RP_SALT)).toString("hex");
out["behavior_hash"] = Buffer.from(normalizeBehavior(BEHAVIOR)).toString("hex");
out["context_hash"] = Buffer.from(normalizeContext(CONTEXT)).toString("hex");

const iv = compileIdentityVector(DEVICE, BEHAVIOR, CONTEXT, RP_SALT);
out["iv_digest"] = iv.ivDigest;
out["iv_vector_first5"] = iv.vector.slice(0, 5).map((x) => x.toFixed(10)).join(",");
out["iv_vector_norm_sq"] = iv.vector.reduce((s, x) => s + x * x, 0).toFixed(10);

console.log(JSON.stringify(out, null, 2));
