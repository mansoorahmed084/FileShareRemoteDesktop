import { useEffect, useState, useCallback } from "react";
import type { ConnectionStatus, PairedDevice } from "../lib/types";
import type { TextMessage } from "../components/TextShare";
import { getConfig, saveConfig } from "../lib/storage";
import { StatusBadge } from "../components/StatusBadge";
import { PairingDialog } from "../components/PairingDialog";
import { DeviceList } from "../components/DeviceList";
import { TextShare } from "../components/TextShare";

type Tab = "devices" | "text" | "settings";

export default function App() {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [serverUrl, setServerUrl] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("devices");

  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [pairingError, setPairingError] = useState<string | null>(null);
  const [verificationEmojis, setVerificationEmojis] = useState<string | null>(null);
  const [verificationDeviceId, setVerificationDeviceId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TextMessage[]>([]);

  const loadDevices = useCallback(() => {
    chrome.runtime.sendMessage({ type: "get_paired_devices" }, (res) => {
      if (res?.devices) setDevices(res.devices);
    });
  }, []);

  useEffect(() => {
    getConfig().then((config) => {
      setServerUrl(config.serverUrl);
      setDeviceName(config.deviceName);
      setDeviceId(config.deviceId);
    });

    chrome.runtime.sendMessage({ type: "get_status" }, (res) => {
      if (res?.status) setStatus(res.status);
    });

    loadDevices();

    const listener = (message: Record<string, unknown>) => {
      switch (message.type) {
        case "status_changed":
          setStatus(message.status as ConnectionStatus);
          break;
        case "pair_code":
          setPairingCode(
            (message.payload as Record<string, string>)?.code || null
          );
          break;
        case "pair_accept":
          setPairingCode(null);
          loadDevices();
          break;
        case "pair_reject":
          setPairingError(message.payload as string);
          break;
        case "device_online":
          setDevices((prev) =>
            prev.map((d) =>
              d.device_id === message.device_id ? { ...d, is_online: true } : d
            )
          );
          break;
        case "device_offline":
          setDevices((prev) =>
            prev.map((d) =>
              d.device_id === message.device_id
                ? { ...d, is_online: false }
                : d
            )
          );
          break;
        case "verification_emojis":
          setVerificationEmojis(message.emojis as string);
          setVerificationDeviceId(message.device_id as string);
          break;
        case "text_received": {
          const newMsg: TextMessage = {
            id: crypto.randomUUID(),
            from: message.from_device as string,
            text: message.text as string,
            timestamp: ((message.timestamp as number) || Date.now() / 1000) * 1000,
            direction: "received",
          };
          setMessages((prev) => [...prev, newMsg]);
          break;
        }
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, [loadDevices]);

  const handleConnect = async () => {
    await saveConfig({ serverUrl, deviceName });
    chrome.runtime.sendMessage({ type: "connect", serverUrl });
  };

  const handleDisconnect = () => {
    chrome.runtime.sendMessage({ type: "disconnect" });
  };

  const handleSendText = (text: string) => {
    if (!selectedDeviceId) return;
    chrome.runtime.sendMessage({
      type: "send_text",
      to_device: selectedDeviceId,
      text,
    });
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        from: deviceId,
        text,
        timestamp: Date.now(),
        direction: "sent",
      },
    ]);
  };

  const selectedDevice = devices.find((d) => d.device_id === selectedDeviceId);

  const tabs: { id: Tab; label: string }[] = [
    { id: "devices", label: "Devices" },
    { id: "text", label: "Text" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="w-96 min-h-[480px] bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-base font-bold">RemoteDesktop</h1>
        <StatusBadge status={status} />
      </div>

      {status !== "connected" ? (
        <div className="p-4 space-y-3">
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
            />
          </div>
          <div className="text-xs text-gray-400 font-mono truncate">
            ID: {deviceId}
          </div>
          <button
            onClick={handleConnect}
            disabled={status === "connecting"}
            className="w-full py-2 px-4 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {status === "connecting" ? "Connecting..." : "Connect"}
          </button>
        </div>
      ) : (
        <>
          <div className="flex border-b border-gray-200 dark:border-gray-700">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 text-xs font-medium transition-colors ${
                  activeTab === tab.id
                    ? "text-primary-600 border-b-2 border-primary-600"
                    : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="p-4">
            {activeTab === "devices" && (
              <div className="space-y-4">
                <DeviceList
                  devices={devices}
                  selectedDeviceId={selectedDeviceId}
                  onSelect={(id) => {
                    setSelectedDeviceId(id);
                    setActiveTab("text");
                  }}
                  onRemove={(id) => {
                    chrome.runtime.sendMessage({ type: "unpair", device_id: id });
                    setDevices((prev) => prev.filter((d) => d.device_id !== id));
                    if (selectedDeviceId === id) setSelectedDeviceId(null);
                  }}
                />
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <PairingDialog
                    onCreateCode={() => {
                      setPairingCode(null);
                      setPairingError(null);
                      chrome.runtime.sendMessage({ type: "pair_create" });
                    }}
                    onJoinCode={(code) => {
                      setPairingError(null);
                      chrome.runtime.sendMessage({ type: "pair_join", code });
                    }}
                    pairingCode={pairingCode}
                    verificationEmojis={verificationEmojis}
                    error={pairingError}
                    onConfirmVerification={() => {
                      setVerificationEmojis(null);
                      if (verificationDeviceId) {
                        setSelectedDeviceId(verificationDeviceId);
                      }
                    }}
                    onCancelVerification={() => {
                      setVerificationEmojis(null);
                      setVerificationDeviceId(null);
                    }}
                  />
                </div>
              </div>
            )}

            {activeTab === "text" && (
              <TextShare
                messages={messages.filter(
                  (m) =>
                    m.from === selectedDeviceId || m.direction === "sent"
                )}
                selectedDeviceId={selectedDeviceId}
                selectedDeviceName={selectedDevice?.device_name || null}
                onSend={handleSendText}
                disabled={!selectedDeviceId || !selectedDevice?.is_online}
              />
            )}

            {activeTab === "settings" && (
              <div className="space-y-3">
                <div className="text-xs text-gray-400 font-mono">
                  Device ID: {deviceId}
                </div>
                <div className="text-xs text-gray-400">
                  Server: {serverUrl}
                </div>
                <button
                  onClick={handleDisconnect}
                  className="w-full py-2 px-4 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
                >
                  Disconnect
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
