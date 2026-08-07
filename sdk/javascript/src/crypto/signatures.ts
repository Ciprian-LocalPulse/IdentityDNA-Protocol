/** Ed25519 signing, mirrors reference/crypto/signatures.py. RFC-0001 §11.1 / RFC 8032. */
import { ed25519 } from "@noble/curves/ed25519.js";

function toBase64(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64");
}
function fromBase64(b64: string): Uint8Array {
  return new Uint8Array(Buffer.from(b64, "base64"));
}

export class SigningKeyPair {
  private constructor(
    private readonly secretKey: Uint8Array,
    public readonly publicKey: Uint8Array
  ) {}

  static generate(): SigningKeyPair {
    const sk = ed25519.utils.randomSecretKey();
    const pk = ed25519.getPublicKey(sk);
    return new SigningKeyPair(sk, pk);
  }

  get publicKeyB64(): string {
    return toBase64(this.publicKey);
  }

  /** Signs a transcript hash (RFC-0001 §11.2), not raw fields, so the
   * proof is bound to the entire handshake so far. */
  sign(transcriptHash: Uint8Array): string {
    const sig = ed25519.sign(transcriptHash, this.secretKey);
    return toBase64(sig);
  }
}

export function verifySignature(publicKeyB64: string, transcriptHash: Uint8Array, signatureB64: string): boolean {
  try {
    return ed25519.verify(fromBase64(signatureB64), transcriptHash, fromBase64(publicKeyB64));
  } catch {
    return false;
  }
}
