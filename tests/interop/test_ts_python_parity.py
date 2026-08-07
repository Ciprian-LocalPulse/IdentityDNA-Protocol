"""
Cross-language interoperability regression test: the TypeScript SDK
(sdk/javascript/) and the Python reference implementation
(reference/) MUST produce byte-identical cryptographic digests for the
same inputs. This is what "interoperable" actually means for a
protocol -- not "looks similar", but "produces the same bytes".

This test shells out to `npx tsx` to run the TS fixture printer, and
compares its output against the equivalent Python computation. Requires
Node.js + the SDK's npm dependencies to be installed
(sdk/javascript/node_modules), so this is skipped (not failed) if that
environment isn't available -- it's an interop check, not a core
protocol test that must run everywhere.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SDK_JS = _REPO_ROOT / "sdk" / "javascript"
_REF = _REPO_ROOT / "reference"
for p in ["", "identity-engine", "entropy-engine"]:
    sys.path.insert(0, str(_REF / p) if p else str(_REF))


def _node_modules_available() -> bool:
    return (_SDK_JS / "node_modules").is_dir()


@pytest.mark.skipif(not _node_modules_available(), reason="sdk/javascript/node_modules not installed (run `npm install` in sdk/javascript)")
def test_typescript_and_python_produce_identical_digests():
    from crypto import hash_blake3, hkdf
    from normalizer import normalize_device, normalize_behavior, normalize_context
    from identity_vector import compile_identity_vector

    DEVICE = {"platform": "Linux", "screen_class": "1920x1080", "timezone_offset_min": 120,
              "language": "ro", "color_depth_class": "24bit", "hardware_concurrency_class": "4-8",
              "gpu_vendor_class": "intel"}
    BEHAVIOR = {"typing_cadence_ms": [120, 110, 130, 125], "pointer_entropy": 0.42}
    CONTEXT = {"tz_offset_min": 120, "locale": "ro-RO"}
    RP_SALT = "demo-rp-salt-v1"

    py = {}
    py["hash_domain_a"] = hash_blake3(b"same-input", domain="DOMAIN-A").hex()
    py["hash_domain_b"] = hash_blake3(b"same-input", domain="DOMAIN-B").hex()
    py["hkdf_basic"] = hkdf(b"ikm-material", salt=b"salt", info="test", length=48).hex()
    py["device_hash"] = normalize_device(DEVICE, RP_SALT).hex()
    py["behavior_hash"] = normalize_behavior(BEHAVIOR).hex()
    py["context_hash"] = normalize_context(CONTEXT).hex()
    iv = compile_identity_vector(DEVICE, BEHAVIOR, CONTEXT, RP_SALT)
    py["iv_digest"] = iv.iv_digest
    py["iv_vector_first5"] = ",".join(f"{x:.10f}" for x in iv.vector[:5])
    py["iv_vector_norm_sq"] = f"{sum(x * x for x in iv.vector):.10f}"

    result = subprocess.run(
        ["npx", "tsx", "src/interop/printFixtures.ts"],
        cwd=str(_SDK_JS), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"TS fixture script failed:\n{result.stderr}"
    ts = json.loads(result.stdout)

    for key in py:
        assert ts.get(key) == py[key], f"MISMATCH on '{key}':\n  python: {py[key]}\n  typescript: {ts.get(key)}"
