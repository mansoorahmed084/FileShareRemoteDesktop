import { useEffect, useState } from "react";
import type { ConnectionStatus } from "../lib/types";
import { getConfig, saveConfig } from "../lib/storage";
import { StatusBadge } from "../components/StatusBadge";

export default function App() {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [serverUrl, setServerUrl] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [deviceId, setDeviceId] = useState("");

  useEffect(() => {
    getConfig().then((config) => {
      setServerUrl(config.serverUrl);
      setDeviceName(config.deviceName);
      setDeviceId(config.deviceId);
    });

    chrome.runtime.sendMessage({ type: "get_status" }, (res) => {
      if (res?.status) setStatus(res.status);
    });

    const listener = (message: { type: string; status?: ConnectionStatus }) => {
      if (message.type === "status_changed" && message.status) {
        setStatus(message.status);
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const handleConnect = async () => {
    await saveConfig({ serverUrl, deviceName });
    chrome.runtime.sendMessage({ type: "connect", serverUrl });
  };

  const handleDisconnect = () => {
    chrome.runtime.sendMessage({ type: "disconnect" });
  };

  return (
    <div className="w-80 p-4 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-bold">RemoteDesktop</h1>
        <StatusBadge status={status} />
      </div>

      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            Server URL
          </label>
          <input
            type="text"
            value={serverUrl}
            onChange={(e) => setServerUrl(e.target.value)}
            placeholder="ws://localhost:8765"
            className="w-full px-3 py-2 text-sm border rounded-lg bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            disabled={status === "connected"}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            Device Name
          </label>
          <input
            type="text"
            value={deviceName}
            onChange={(e) => setDeviceName(e.target.value)}
            placeholder="My Laptop"
            className="w-full px-3 py-2 text-sm border rounded-lg bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            disabled={status === "connected"}
          />
        </div>

        <div className="text-xs text-gray-400 font-mono truncate">
          ID: {deviceId}
        </div>

        {status === "connected" ? (
          <button
            onClick={handleDisconnect}
            className="w-full py-2 px-4 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
          >
            Disconnect
          </button>
        ) : (
          <button
            onClick={handleConnect}
            disabled={status === "connecting"}
            className="w-full py-2 px-4 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {status === "connecting" ? "Connecting..." : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}
