import { wsClient } from "../lib/websocket";
import { getConfig, addPairedDevice, removePairedDevice, getPairedDevices } from "../lib/storage";
import {
  generateKeyPair,
  deriveSharedKey,
  encrypt,
  decrypt,
  generateVerificationEmojis,
  type KeyPairData,
} from "../lib/crypto";
import { FileReceiver, type FileMetadata, type TransferProgress } from "../lib/file-transfer";
import type { WSMessage, ConnectionStatus, PairedDevice } from "../lib/types";

let currentStatus: ConnectionStatus = "disconnected";
let keepAliveEnabled = false;

const KEEPALIVE_ALARM = "ws-keepalive";
const KEEPALIVE_INTERVAL_MS = 25000; // 25s — before Chrome's 30s service worker timeout

async function startKeepAlive() {
  if (keepAliveEnabled) return;
  keepAliveEnabled = true;
  await chrome.alarms.create(KEEPALIVE_ALARM, { periodInMinutes: 0.4 }); // ~24s
}

async function stopKeepAlive() {
  keepAliveEnabled = false;
  await chrome.alarms.clear(KEEPALIVE_ALARM);
}

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === KEEPALIVE_ALARM) {
    if (wsClient.status === "disconnected" || wsClient.status === "error") {
      const config = await getConfig();
      if (config.autoConnect && config.serverUrl) {
        wsClient.connect(config.serverUrl, config.deviceId, config.deviceName);
      }
    }
  }
});

const pendingKeyExchange = new Map<
  string,
  { keyPair: KeyPairData; peerPublicKey?: JsonWebKey }
>();
const sharedKeys = new Map<string, CryptoKey>();
const activeReceivers = new Map<string, FileReceiver>();
const receiveProgress = new Map<string, TransferProgress>();
const receivedBlobs = new Map<string, Blob>();

async function init() {
  const config = await getConfig();

  wsClient.onStatus(async (status) => {
    currentStatus = status;
    broadcastToExtension({ type: "status_changed", status });
    if (status === "connected") {
      await startKeepAlive();
    } else if (status === "disconnected") {
      // Don't stop keepalive on disconnect — let it try to reconnect
    }
  });

  wsClient.onMessage(async (msg: WSMessage) => {
    switch (msg.type) {
      case "pair_code":
        broadcastToExtension({ type: "pair_code", payload: msg.payload });
        break;

      case "pair_accept": {
        if (!msg.from_device) break;
        const payload = msg.payload as Record<string, unknown> | undefined;
        const device: PairedDevice = {
          device_id: msg.from_device,
          device_name: (payload?.device_name as string) || "Unknown",
          is_online: true,
          paired_at: Date.now(),
        };
        await addPairedDevice(device);
        broadcastToExtension({ type: "pair_accept", device });
        await initiateKeyExchange(msg.from_device);
        break;
      }

      case "pair_reject":
        broadcastToExtension({ type: "pair_reject", payload: msg.payload });
        break;

      case "key_exchange": {
        if (!msg.from_device) break;
        const kxPayload = msg.payload as Record<string, unknown>;
        const peerPublicKey = kxPayload?.publicKey as JsonWebKey;
        if (!peerPublicKey) break;

        const pending = pendingKeyExchange.get(msg.from_device);
        if (pending) {
          pending.peerPublicKey = peerPublicKey;
          const sharedKey = await deriveSharedKey(pending.keyPair.privateKey, peerPublicKey);
          sharedKeys.set(msg.from_device, sharedKey);
          const emojis = await generateVerificationEmojis(pending.keyPair.publicKey, peerPublicKey);
          broadcastToExtension({
            type: "verification_emojis",
            device_id: msg.from_device,
            emojis,
          });
          pendingKeyExchange.delete(msg.from_device);
        } else {
          const keyPair = await generateKeyPair();
          const sharedKey = await deriveSharedKey(keyPair.privateKey, peerPublicKey);
          sharedKeys.set(msg.from_device, sharedKey);

          const cfg = await getConfig();
          wsClient.send({
            type: "key_exchange",
            from_device: cfg.deviceId,
            to_device: msg.from_device,
            payload: { publicKey: keyPair.publicKey },
          });

          const emojis = await generateVerificationEmojis(keyPair.publicKey, peerPublicKey);
          broadcastToExtension({
            type: "verification_emojis",
            device_id: msg.from_device,
            emojis,
          });
        }
        break;
      }

      case "text": {
        if (!msg.from_device) break;
        const textPayload = msg.payload as Record<string, unknown>;
        const ciphertext = textPayload?.ciphertext as string;
        const nonce = textPayload?.nonce as string;

        if (ciphertext && nonce) {
          const key = sharedKeys.get(msg.from_device);
          if (key) {
            try {
              const plaintext = await decrypt(key, ciphertext, nonce);
              broadcastToExtension({
                type: "text_received",
                from_device: msg.from_device,
                text: plaintext,
                timestamp: msg.timestamp,
              });
            } catch {
              broadcastToExtension({ type: "error", payload: "Failed to decrypt message" });
            }
          }
        } else {
          broadcastToExtension({
            type: "text_received",
            from_device: msg.from_device,
            text: (textPayload?.text as string) || "",
            timestamp: msg.timestamp,
          });
        }
        break;
      }

      case "file_meta": {
        if (!msg.from_device) break;
        const meta = msg.payload as unknown as FileMetadata;
        const key = sharedKeys.get(msg.from_device) || null;
        const receiver = new FileReceiver(meta, key);
        activeReceivers.set(meta.transferId, receiver);
        receiveProgress.set(meta.transferId, {
          transferId: meta.transferId,
          fileName: meta.fileName,
          fileSize: meta.fileSize,
          totalChunks: meta.totalChunks,
          completedChunks: 0,
          direction: "receive",
          status: "active",
          startTime: Date.now(),
        });

        const cfg = await getConfig();
        wsClient.send({
          type: "file_ack",
          from_device: cfg.deviceId,
          to_device: msg.from_device,
          payload: { transferId: meta.transferId, status: "ready" },
        });

        broadcastToExtension({
          type: "transfer_update",
          transfer: receiveProgress.get(meta.transferId),
        });
        break;
      }

      case "file_chunk": {
        if (!msg.from_device) break;
        const chunkPayload = msg.payload as Record<string, unknown>;
        const transferId = chunkPayload.transferId as string;
        const chunkIndex = chunkPayload.index as number;
        const chunkData = chunkPayload.data as string;
        const chunkNonce = chunkPayload.nonce as string;

        const receiver = activeReceivers.get(transferId);
        const progress = receiveProgress.get(transferId);
        if (!receiver || !progress) break;

        try {
          await receiver.addChunk(chunkIndex, chunkData, chunkNonce);
          progress.completedChunks = chunkIndex + 1;

          if (receiver.isComplete) {
            const { blob, verified } = await receiver.assemble();
            receivedBlobs.set(transferId, blob);
            progress.status = "complete";
            if (!verified) {
              progress.error = "Hash mismatch — file may be corrupted";
            }
            activeReceivers.delete(transferId);
          }

          broadcastToExtension({ type: "transfer_update", transfer: { ...progress } });
        } catch (err) {
          progress.status = "failed";
          progress.error = String(err);
          activeReceivers.delete(transferId);
          broadcastToExtension({ type: "transfer_update", transfer: { ...progress } });
        }
        break;
      }

      case "file_ack": {
        const ackPayload = msg.payload as Record<string, unknown>;
        broadcastToExtension({
          type: "file_ack",
          transferId: ackPayload.transferId,
          status: ackPayload.status,
        });
        break;
      }

      case "file_cancel": {
        const cancelPayload = msg.payload as Record<string, unknown>;
        const tid = cancelPayload.transferId as string;
        activeReceivers.delete(tid);
        const prog = receiveProgress.get(tid);
        if (prog) {
          prog.status = "cancelled";
          broadcastToExtension({ type: "transfer_update", transfer: { ...prog } });
        }
        break;
      }

      case "device_online":
        broadcastToExtension({
          type: "device_online",
          device_id: msg.from_device,
          payload: msg.payload,
        });
        break;

      case "device_offline":
        broadcastToExtension({
          type: "device_offline",
          device_id: msg.from_device,
        });
        break;

      default:
        broadcastToExtension({ type: "ws_message", msg });
    }
  });

  if (config.autoConnect && config.serverUrl) {
    wsClient.connect(config.serverUrl, config.deviceId, config.deviceName);
    await startKeepAlive();
  }
}

async function initiateKeyExchange(targetDeviceId: string) {
  const keyPair = await generateKeyPair();
  pendingKeyExchange.set(targetDeviceId, { keyPair });
  const config = await getConfig();
  wsClient.send({
    type: "key_exchange",
    from_device: config.deviceId,
    to_device: targetDeviceId,
    payload: { publicKey: keyPair.publicKey },
  });
}

function broadcastToExtension(message: Record<string, unknown>) {
  chrome.runtime.sendMessage(message).catch(() => {});
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    switch (message.type) {
      case "get_status":
        sendResponse({ status: currentStatus });
        break;

      case "connect": {
        const config = await getConfig();
        wsClient.connect(
          message.serverUrl || config.serverUrl,
          config.deviceId,
          config.deviceName
        );
        await startKeepAlive();
        sendResponse({ ok: true });
        break;
      }

      case "disconnect":
        wsClient.disconnect();
        await stopKeepAlive();
        sendResponse({ ok: true });
        break;

      case "pair_create":
        wsClient.send({ type: "pair_create" });
        sendResponse({ ok: true });
        break;

      case "pair_join":
        wsClient.send({ type: "pair_join", payload: { code: message.code } });
        sendResponse({ ok: true });
        break;

      case "unpair": {
        const config = await getConfig();
        wsClient.send({
          type: "unpair",
          from_device: config.deviceId,
          to_device: message.device_id,
        });
        await removePairedDevice(message.device_id);
        sharedKeys.delete(message.device_id);
        sendResponse({ ok: true });
        break;
      }

      case "send_text": {
        const config = await getConfig();
        const key = sharedKeys.get(message.to_device);
        if (key) {
          const { ciphertext, nonce } = await encrypt(key, message.text);
          wsClient.send({
            type: "text",
            from_device: config.deviceId,
            to_device: message.to_device,
            payload: { ciphertext, nonce },
            timestamp: Date.now() / 1000,
          });
        } else {
          wsClient.send({
            type: "text",
            from_device: config.deviceId,
            to_device: message.to_device,
            payload: { text: message.text },
            timestamp: Date.now() / 1000,
          });
        }
        sendResponse({ ok: true });
        break;
      }

      case "send_file": {
        const config = await getConfig();
        const { to_device, meta, chunks } = message as {
          to_device: string;
          meta: FileMetadata;
          chunks: { index: number; total: number; data: string; nonce: string }[];
        };

        wsClient.send({
          type: "file_meta",
          from_device: config.deviceId,
          to_device,
          payload: meta as unknown as Record<string, unknown>,
          timestamp: Date.now() / 1000,
        });

        for (const chunk of chunks) {
          wsClient.send({
            type: "file_chunk",
            from_device: config.deviceId,
            to_device,
            payload: {
              transferId: meta.transferId,
              index: chunk.index,
              total: chunk.total,
              data: chunk.data,
              nonce: chunk.nonce,
            },
            timestamp: Date.now() / 1000,
          });
        }
        sendResponse({ ok: true });
        break;
      }

      case "cancel_transfer": {
        const config = await getConfig();
        wsClient.send({
          type: "file_cancel",
          from_device: config.deviceId,
          to_device: message.to_device,
          payload: { transferId: message.transferId },
        });
        sendResponse({ ok: true });
        break;
      }

      case "download_received": {
        const blob = receivedBlobs.get(message.transferId);
        if (blob) {
          const buffer = await blob.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          const chunkSize = 8192;
          let binary = "";
          for (let i = 0; i < bytes.length; i += chunkSize) {
            binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
          }
          const base64 = btoa(binary);
          const mimeType = blob.type || "application/octet-stream";
          await chrome.downloads.download({
            url: `data:${mimeType};base64,${base64}`,
            filename: message.fileName,
            saveAs: true,
          });
          sendResponse({ ok: true });
        } else {
          sendResponse({ error: "File not found" });
        }
        break;
      }

      case "get_paired_devices": {
        const devices = await getPairedDevices();
        sendResponse({ devices });
        break;
      }

      case "get_transfers": {
        sendResponse({ transfers: Array.from(receiveProgress.values()) });
        break;
      }

      case "has_shared_key":
        sendResponse({ hasKey: sharedKeys.has(message.device_id) });
        break;

      case "initiate_key_exchange":
        await initiateKeyExchange(message.device_id);
        sendResponse({ ok: true });
        break;

      default:
        sendResponse({ error: "Unknown message type" });
    }
  })();
  return true;
});

init();
