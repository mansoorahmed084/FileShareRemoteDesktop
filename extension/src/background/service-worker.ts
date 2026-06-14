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
import type { WSMessage, ConnectionStatus, PairedDevice } from "../lib/types";

let currentStatus: ConnectionStatus = "disconnected";

const pendingKeyExchange = new Map<
  string,
  { keyPair: KeyPairData; peerPublicKey?: JsonWebKey }
>();
const sharedKeys = new Map<string, CryptoKey>();

async function init() {
  const config = await getConfig();

  wsClient.onStatus((status) => {
    currentStatus = status;
    broadcastToExtension({ type: "status_changed", status });
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
          const sharedKey = await deriveSharedKey(
            pending.keyPair.privateKey,
            peerPublicKey
          );
          sharedKeys.set(msg.from_device, sharedKey);
          const emojis = await generateVerificationEmojis(
            pending.keyPair.publicKey,
            peerPublicKey
          );
          broadcastToExtension({
            type: "verification_emojis",
            device_id: msg.from_device,
            emojis,
          });
          pendingKeyExchange.delete(msg.from_device);
        } else {
          const keyPair = await generateKeyPair();
          const sharedKey = await deriveSharedKey(
            keyPair.privateKey,
            peerPublicKey
          );
          sharedKeys.set(msg.from_device, sharedKey);

          const cfg = await getConfig();
          wsClient.send({
            type: "key_exchange",
            from_device: cfg.deviceId,
            to_device: msg.from_device,
            payload: { publicKey: keyPair.publicKey },
          });

          const emojis = await generateVerificationEmojis(
            keyPair.publicKey,
            peerPublicKey
          );
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
              broadcastToExtension({
                type: "error",
                payload: "Failed to decrypt message",
              });
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
        sendResponse({ ok: true });
        break;
      }

      case "disconnect":
        wsClient.disconnect();
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

      case "get_paired_devices": {
        const devices = await getPairedDevices();
        sendResponse({ devices });
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
