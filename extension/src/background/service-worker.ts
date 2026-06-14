import { wsClient } from "../lib/websocket";
import { getConfig, addPairedDevice } from "../lib/storage";
import type { WSMessage, ConnectionStatus, PairedDevice } from "../lib/types";

let currentStatus: ConnectionStatus = "disconnected";

async function init() {
  const config = await getConfig();

  wsClient.onStatus((status) => {
    currentStatus = status;
    chrome.runtime.sendMessage({ type: "status_changed", status }).catch(() => {});
  });

  wsClient.onMessage(async (msg: WSMessage) => {
    switch (msg.type) {
      case "pair_code":
        chrome.runtime.sendMessage({ type: "pair_code", payload: msg.payload }).catch(() => {});
        break;

      case "pair_accept":
        if (msg.from_device) {
          const payload = msg.payload as Record<string, unknown> | undefined;
          const device: PairedDevice = {
            device_id: msg.from_device,
            device_name: (payload?.device_name as string) || "Unknown",
            is_online: true,
            paired_at: Date.now(),
          };
          await addPairedDevice(device);
          chrome.runtime.sendMessage({ type: "pair_accept", device }).catch(() => {});
        }
        break;

      case "pair_reject":
        chrome.runtime.sendMessage({ type: "pair_reject", payload: msg.payload }).catch(() => {});
        break;

      case "device_online":
        chrome.runtime.sendMessage({
          type: "device_online",
          device_id: msg.from_device,
          payload: msg.payload,
        }).catch(() => {});
        break;

      case "device_offline":
        chrome.runtime.sendMessage({
          type: "device_offline",
          device_id: msg.from_device,
        }).catch(() => {});
        break;

      case "text":
        chrome.runtime.sendMessage({ type: "text_received", msg }).catch(() => {});
        break;

      default:
        chrome.runtime.sendMessage({ type: "ws_message", msg }).catch(() => {});
    }
  });

  if (config.autoConnect && config.serverUrl) {
    wsClient.connect(config.serverUrl, config.deviceId, config.deviceName);
  }
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

      case "send_ws":
        sendResponse({ ok: wsClient.send(message.msg) });
        break;

      case "pair_create":
        wsClient.send({ type: "pair_create" });
        sendResponse({ ok: true });
        break;

      case "pair_join":
        wsClient.send({ type: "pair_join", payload: { code: message.code } });
        sendResponse({ ok: true });
        break;

      case "send_text": {
        const config = await getConfig();
        wsClient.send({
          type: "text",
          from_device: config.deviceId,
          to_device: message.to_device,
          payload: message.text,
          timestamp: Date.now() / 1000,
        });
        sendResponse({ ok: true });
        break;
      }

      default:
        sendResponse({ error: "Unknown message type" });
    }
  })();
  return true;
});

init();
