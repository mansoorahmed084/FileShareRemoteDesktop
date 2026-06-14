import { encryptBuffer, decryptBuffer, bufferToBase64, base64ToBuffer } from "./crypto";

const CHUNK_SIZE = 64 * 1024; // 64KB

export interface FileMetadata {
  transferId: string;
  fileName: string;
  fileSize: number;
  fileType: string;
  totalChunks: number;
  sha256: string;
}

export interface TransferProgress {
  transferId: string;
  fileName: string;
  fileSize: number;
  totalChunks: number;
  completedChunks: number;
  direction: "send" | "receive";
  status: "pending" | "active" | "complete" | "failed" | "cancelled";
  startTime: number;
  error?: string;
}

export async function hashFile(data: ArrayBuffer): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function createFileMetadata(file: File): Omit<FileMetadata, "sha256"> {
  return {
    transferId: crypto.randomUUID(),
    fileName: file.name,
    fileSize: file.size,
    fileType: file.type || "application/octet-stream",
    totalChunks: Math.ceil(file.size / CHUNK_SIZE),
  };
}

export async function* chunkFile(
  file: File,
  encryptionKey: CryptoKey | null
): AsyncGenerator<{ index: number; total: number; data: string; nonce: string }> {
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  const arrayBuffer = await file.arrayBuffer();

  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const chunk = arrayBuffer.slice(start, end);

    if (encryptionKey) {
      const { ciphertext, nonce } = await encryptBuffer(encryptionKey, chunk);
      yield {
        index: i,
        total: totalChunks,
        data: bufferToBase64(ciphertext),
        nonce: bufferToBase64(nonce.buffer as ArrayBuffer),
      };
    } else {
      yield {
        index: i,
        total: totalChunks,
        data: bufferToBase64(chunk),
        nonce: "",
      };
    }
  }
}

export class FileReceiver {
  private chunks = new Map<number, ArrayBuffer>();
  private metadata: FileMetadata;
  private encryptionKey: CryptoKey | null;

  constructor(metadata: FileMetadata, encryptionKey: CryptoKey | null) {
    this.metadata = metadata;
    this.encryptionKey = encryptionKey;
  }

  get progress(): number {
    return this.chunks.size / this.metadata.totalChunks;
  }

  get isComplete(): boolean {
    return this.chunks.size === this.metadata.totalChunks;
  }

  async addChunk(index: number, data: string, nonce: string): Promise<void> {
    const raw = base64ToBuffer(data);

    if (this.encryptionKey && nonce) {
      const nonceBytes = new Uint8Array(base64ToBuffer(nonce));
      const decrypted = await decryptBuffer(this.encryptionKey, raw, nonceBytes);
      this.chunks.set(index, decrypted);
    } else {
      this.chunks.set(index, raw);
    }
  }

  async assemble(): Promise<{ blob: Blob; verified: boolean }> {
    const parts: ArrayBuffer[] = [];
    for (let i = 0; i < this.metadata.totalChunks; i++) {
      const chunk = this.chunks.get(i);
      if (!chunk) throw new Error(`Missing chunk ${i}`);
      parts.push(chunk);
    }

    const combined = new Uint8Array(
      parts.reduce((acc, p) => acc + p.byteLength, 0)
    );
    let offset = 0;
    for (const part of parts) {
      combined.set(new Uint8Array(part), offset);
      offset += part.byteLength;
    }

    const hash = await hashFile(combined.buffer);
    const verified = hash === this.metadata.sha256;

    const blob = new Blob([combined], { type: this.metadata.fileType });
    return { blob, verified };
  }
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function formatSpeed(bytesPerSecond: number): string {
  return `${formatFileSize(bytesPerSecond)}/s`;
}
