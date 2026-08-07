/** X25519 ephemeral key agreement, mirrors reference/crypto/keyagreement.py.
 * RFC-0001 §11.1 / RFC 7748. */
import { x25519 } from "@noble/curves/ed25519.js";

function toBase64(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64");
}
function fromBase64(b64: string): Uint8Array {
  return new Uint8Array(Buffer.from(b64, "base64"));
}

export class EphemeralKeyPair {
  private constructor(
    private readonly secretKey: Uint8Array,
    public readonly publicKey: Uint8Array
  ) {}

  static generate(): EphemeralKeyPair {
    const sk = x25519.utils.randomSecretKey();
    const pk = x25519.getPublicKey(sk);
    return new EphemeralKeyPair(sk, pk);
  }

  get publicKeyB64(): string {
    return toBase64(this.publicKey);
  }

  /** Raw X25519 shared secret (32 bytes). MUST be run through HKDF
   * before use as key material — never used raw (RFC-0001 §9). */
  ecdh(peerPublicKeyB64: string): Uint8Array {
    return x25519.getSharedSecret(this.secretKey, fromBase64(peerPublicKeyB64));
  }
}
