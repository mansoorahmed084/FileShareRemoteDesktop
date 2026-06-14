const ECDH_ALGORITHM = { name: "ECDH", namedCurve: "P-256" };
const AES_ALGORITHM = "AES-GCM";
const AES_KEY_LENGTH = 256;
const NONCE_LENGTH = 12;

export interface KeyPairData {
  publicKey: JsonWebKey;
  privateKey: CryptoKey;
}

export async function generateKeyPair(): Promise<KeyPairData> {
  const keyPair = await crypto.subtle.generateKey(ECDH_ALGORITHM, true, [
    "deriveKey",
    "deriveBits",
  ]);
  const publicKey = await crypto.subtle.exportKey("jwk", keyPair.publicKey);
  return { publicKey, privateKey: keyPair.privateKey };
}

export async function deriveSharedKey(
  privateKey: CryptoKey,
  peerPublicKeyJwk: JsonWebKey
): Promise<CryptoKey> {
  const peerPublicKey = await crypto.subtle.importKey(
    "jwk",
    peerPublicKeyJwk,
    ECDH_ALGORITHM,
    false,
    []
  );

  const sharedBits = await crypto.subtle.deriveBits(
    { name: "ECDH", public: peerPublicKey },
    privateKey,
    256
  );

  const hkdfKey = await crypto.subtle.importKey(
    "raw",
    sharedBits,
    "HKDF",
    false,
    ["deriveKey"]
  );

  return crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: new TextEncoder().encode("RemoteDesktop-v1"),
      info: new TextEncoder().encode("aes-key"),
    },
    hkdfKey,
    { name: AES_ALGORITHM, length: AES_KEY_LENGTH },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encrypt(
  key: CryptoKey,
  plaintext: string
): Promise<{ ciphertext: string; nonce: string }> {
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LENGTH));
  const encoded = new TextEncoder().encode(plaintext);

  const encrypted = await crypto.subtle.encrypt(
    { name: AES_ALGORITHM, iv: nonce },
    key,
    encoded
  );

  return {
    ciphertext: bufferToBase64(encrypted),
    nonce: bufferToBase64(nonce.buffer),
  };
}

export async function decrypt(
  key: CryptoKey,
  ciphertext: string,
  nonce: string
): Promise<string> {
  const decrypted = await crypto.subtle.decrypt(
    { name: AES_ALGORITHM, iv: base64ToBuffer(nonce) },
    key,
    base64ToBuffer(ciphertext)
  );

  return new TextDecoder().decode(decrypted);
}

export async function encryptBuffer(
  key: CryptoKey,
  data: ArrayBuffer
): Promise<{ ciphertext: ArrayBuffer; nonce: Uint8Array }> {
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_LENGTH));
  const ciphertext = await crypto.subtle.encrypt(
    { name: AES_ALGORITHM, iv: nonce },
    key,
    data
  );
  return { ciphertext, nonce };
}

export async function decryptBuffer(
  key: CryptoKey,
  ciphertext: ArrayBuffer,
  nonce: Uint8Array
): Promise<ArrayBuffer> {
  return crypto.subtle.decrypt(
    { name: AES_ALGORITHM, iv: nonce as unknown as BufferSource },
    key,
    ciphertext
  );
}

const VERIFICATION_EMOJIS = [
  "🔒", "🛡️", "🔑", "⚡", "🌟", "🎯", "🔥", "💎",
  "🌀", "🎲", "🧩", "🎪", "🌈", "🍀", "🦊", "🐋",
];

export async function generateVerificationEmojis(
  publicKeyA: JsonWebKey,
  publicKeyB: JsonWebKey
): Promise<string> {
  const combined = JSON.stringify([publicKeyA, publicKeyB].sort((a, b) =>
    JSON.stringify(a).localeCompare(JSON.stringify(b))
  ));
  const hash = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(combined)
  );
  const bytes = new Uint8Array(hash);
  return [0, 1, 2, 3]
    .map((i) => VERIFICATION_EMOJIS[bytes[i] % VERIFICATION_EMOJIS.length])
    .join("");
}

function bufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

export { bufferToBase64, base64ToBuffer };
