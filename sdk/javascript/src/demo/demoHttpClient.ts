/**
 * HTTP client demo (TypeScript) -- the JS/TS counterpart to
 * tests/integration/demo_http_client.py. Drives the Python FastAPI
 * reference server (reference/server/api.py) over real HTTP from a
 * TypeScript client, proving genuine cross-language interoperability:
 * a JS-generated Ed25519 proof, verified by the Python server, against
 * a transcript hash computed independently on both sides.
 *
 * Prerequisite: start the server first (see reference/server/README or
 * the main README):
 *   cd reference/server && python -m uvicorn api:app --reload --port 8123
 *
 * Then run:
 *   npm run demo
 *   # or: tsx src/demo/demoHttpClient.ts [baseUrl]
 */
import { ClientSession } from "../verifier/clientSession.js";
import { normalizeDevice } from "../entropy/normalizer.js";

const BASE_URL = process.argv[2] ?? "http://127.0.0.1:8123";
const RP_SALT = "reference-server-rp-salt-v1"; // must match reference/server/api.py's RP_SALT

async function checkServerUp(): Promise<void> {
  try {
    const r = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error(`status ${r.status}`);
  } catch {
    console.error(`ERROR: could not reach ${BASE_URL}.`);
    console.error("Start the server first, in another terminal:");
    console.error("    cd reference/server");
    console.error("    python -m uvicorn api:app --reload --port 8123");
    process.exit(1);
  }
}

async function postJson(path: string, body: unknown): Promise<any> {
  const r = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(`${path} -> ${r.status}: ${JSON.stringify(data)}`);
  return data;
}

async function run(subjectId = "user-ts-sdk-demo"): Promise<void> {
  await checkServerUp();

  console.log(`[1/8] POST /consent  (subject_id=${subjectId})`);
  const consent = await postJson("/consent", { subject_id: subjectId });
  console.log("      ->", consent);

  const client = new ClientSession();
  const hello = client.buildHello();
  console.log("\n[2/8] POST /authenticate  (HELLO ->)");
  const auth = await postJson("/authenticate", { envelope: hello });
  const handshakeId = auth.handshake_id;
  const challenge = auth.challenge;
  console.log("      <- CHALLENGE", challenge.msg_id);

  const deviceRaw = {
    platform: "Node.js", screen_class: "N/A-serverside", timezone_offset_min: 120,
    language: "ro", color_depth_class: "24bit", hardware_concurrency_class: "4-8",
    gpu_vendor_class: "n/a",
  };
  const deviceHash = Buffer.from(normalizeDevice(deviceRaw, RP_SALT)).toString("hex");
  const behaviorRaw = { typing_cadence_ms: [121, 119, 133, 117, 124], pointer_entropy: 0.41 };
  const contextRaw = { tz_offset_min: 120, locale: "ro-RO" };

  const entropy = client.buildEntropy(deviceHash, behaviorRaw, contextRaw, consent.consent_receipt_id);
  console.log("\n[3/8] POST /identity  (ENTROPY ->)");
  const identityResp = await postJson("/identity", {
    handshake_id: handshakeId, envelope: entropy,
    device_raw: deviceRaw, behavior_raw: behaviorRaw, context_raw: contextRaw,
  });
  const ack = identityResp.identity_ack;
  console.log("      <- IDENTITY_ACK", ack.body.iv_digest.slice(0, 16));

  const proof = client.buildProof(hello, challenge, entropy, ack);
  console.log("\n[4/8] POST /verify  (PROOF -> Ed25519 signature generated in TypeScript)");
  const result = await postJson("/verify", {
    handshake_id: handshakeId, envelope: proof,
    context_priors: [0.9, 0.85],
    risk_context: { attempts_last_minute: 1, ip_reputation_score: 90 },
  });
  console.log("      <- TRUST_RESULT (verified server-side, in Python)");
  console.log(JSON.stringify(result.trust_result.body, null, 8));

  const sdna = result.session_dna;
  if (!sdna) {
    console.log("\n(No SESSION_DNA — decision was DENY. Run this script again to");
    console.log(" see the trust score improve, same as the Python CLI persistence demo.)");
    return;
  }

  const sdnaBody = sdna.body;
  console.log("\n[5/8] SESSION_DNA issued:", sdnaBody.session_id);

  console.log("\n[6/8] POST /renew  (rotate SDNA)");
  const renewed = await postJson("/renew", { session_id: sdnaBody.session_id, sdna_b64: sdnaBody.sdna });
  console.log("      ->", renewed);

  console.log("\n[7/8] GET /session/{id}");
  const sessionInfo = await fetch(`${BASE_URL}/session/${sdnaBody.session_id}`).then((r) => r.json());
  console.log("      ->", sessionInfo);

  console.log("\n[8/8] DELETE /session/{id}  (revoke)");
  const revoked = await fetch(`${BASE_URL}/session/${sdnaBody.session_id}`, { method: "DELETE" }).then((r) => r.json());
  console.log("      ->", revoked);

  console.log("\nTypeScript -> Python HTTP handshake demo completed successfully.");
}

run().catch((err) => {
  console.error("Demo failed:", err);
  process.exit(1);
});
