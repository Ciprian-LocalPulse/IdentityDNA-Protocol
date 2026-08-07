/**
 * Client-side handshake helper (TypeScript SDK). Mirrors
 * reference/verifier/verifier.py::ClientSession -- builds HELLO,
 * ENTROPY, and the signed PROOF, per RFC-0001 §4.
 */
import { randomUUID } from "node:crypto";
import { SigningKeyPair } from "../crypto/signatures.js";
import { EphemeralKeyPair } from "../crypto/keyAgreement.js";
import { csprngBytes, canonicalJson, hashBlake3 } from "../crypto/primitives.js";
import type { BehaviorRaw, ContextRaw } from "../entropy/normalizer.js";

export interface Envelope<T = unknown> {
  idp: string;
  type: string;
  msg_id: string;
  body: T;
}

/** RFC-0001 §11.2. Must match reference/identity-engine/verification.py::compute_transcript_hash. */
export function computeTranscriptHash(
  hello: Envelope,
  challenge: Envelope,
  entropy: Envelope,
  identityAck: Envelope
): Uint8Array {
  return hashBlake3(
    [canonicalJson(hello), canonicalJson(challenge), canonicalJson(entropy), canonicalJson(identityAck)],
    "IDP-TRANSCRIPT-v1"
  );
}

export class ClientSession {
  readonly signingKey: SigningKeyPair;
  readonly eph: EphemeralKeyPair;

  constructor() {
    this.signingKey = SigningKeyPair.generate();
    this.eph = EphemeralKeyPair.generate();
  }

  buildHello(): Envelope {
    return {
      idp: "1.0",
      type: "HELLO",
      msg_id: randomUUID(),
      body: {
        client_version: "1.0.0-js-sdk",
        supported_suites: ["ed25519-blake3-argon2id"],
        nonce_c: Buffer.from(csprngBytes(32)).toString("base64"),
        client_eph_public: this.eph.publicKeyB64,
      },
    };
  }

  buildEntropy(
    deviceDnaHash: string,
    behaviorRaw: BehaviorRaw,
    contextRaw: ContextRaw,
    consentReceiptId: string
  ): Envelope {
    return {
      idp: "1.0",
      type: "ENTROPY",
      msg_id: randomUUID(),
      body: {
        device_dna_hash: deviceDnaHash,
        behavioral_sample: behaviorRaw,
        context: contextRaw,
        consent_receipt_id: consentReceiptId,
      },
    };
  }

  buildProof(hello: Envelope, challenge: Envelope, entropy: Envelope, identityAck: Envelope): Envelope {
    const transcriptHash = computeTranscriptHash(hello, challenge, entropy, identityAck);
    const signature = this.signingKey.sign(transcriptHash);
    return {
      idp: "1.0",
      type: "PROOF",
      msg_id: randomUUID(),
      body: {
        signature,
        public_key: this.signingKey.publicKeyB64,
      },
    };
  }
}
