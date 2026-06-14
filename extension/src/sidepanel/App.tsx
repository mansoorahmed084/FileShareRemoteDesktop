import { useState, useEffect, useCallback } from "react";
import type { TextMessage } from "../components/TextShare";
import { getConfig, saveConfig } from "../lib/storage";
import { StatusBadge } from "../components/StatusBadge";
import { PairingDialog } from "../components/PairingDialog";
import { DeviceList } from "../components/DeviceList";
import { TextShare } from "../components/TextShare";
import { FileDropZone } from "../components/FileDropZone";
import { TransferProgressList } from "../components/TransferProgress";
import { useConnectionStatus } from "../hooks/useWebSocket";
import { useDevices } from "../hooks/useDevices";
import { useFileTransfer } from "../hooks/useFileTransfer";

type Tab = "devices" | "text" | "files" | "settings";

export default function App() {
  const { status, connect, disconnect } = useConnectionStatus();
  const { devices, removeDevice, setDevices } = useDevices();
  const { transfers, sendFiles, cancelTransfer, downloadFile } = useFileTransfer();

  const [serverUrl, setServerUrl] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("devices");
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [pairingError, setPairingError] = useState<string | null>(null);
  const [verificationEmojis, setVerificationEmojis] = useState<string | null>(null);
  const [verificationDeviceId, setVerificationDeviceId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TextMessage[]>([]);

  useEffect(() => {
    getConfig().then((config) => {
      setServerUrl(config.serverUrl);
      setDeviceName(config.deviceName);
      setDeviceId(config.deviceId);
    });
  }, []);

  useEffect(() => {
    const listener = (message: Record<string, unknown>) => {
      switch (message.type) {
        case "pair_code":
          setPairingCode(
            (message.payload as Record<string, string>)?.code || null
          );
          break;
        case "pair_reject":
          setPairingError(message.payload as string);
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
  }, []);

  const handleConnect = async () => {
    await saveConfig({ serverUrl, deviceName });
    connect(serverUrl);
  };

  const handleSendText = useCallback(
    (text: string) => {
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
    },
    [selectedDeviceId, deviceId]
  );

  const selectedDevice = devices.find((d) => d.device_id === selectedDeviceId);

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "devices", label: "Devices", icon: "💻" },
    { id: "text", label: "Text", icon: "💬" },
    { id: "files", label: "Files", icon: "📁" },
    { id: "settings", label: "Settings", icon: "⚙️" },
  ];

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          <h1 className="text-base font-bold">RemoteDesktop</h1>
          <span className="text-xs text-gray-400 font-mono">v0.1.0</span>
        </div>
        <StatusBadge status={status} />
      </div>

      {status !== "connected" ? (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-sm space-y-4">
            <div className="text-center mb-6">
              <div className="text-4xl mb-2">🔗</div>
              <h2 className="text-lg font-semibold">Connect to Server</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Enter your relay server URL to get started
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Server URL
              </label>
              <input
                type="text"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder="ws://localhost:8765"
                className="w-full px-3 py-2.5 text-sm border rounded-lg bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
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
                className="w-full px-3 py-2.5 text-sm border rounded-lg bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
              />
            </div>
            <button
              onClick={handleConnect}
              disabled={status === "connecting"}
              className="w-full py-2.5 px-4 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {status === "connecting" ? "Connecting..." : "Connect"}
            </button>
            <div className="text-xs text-gray-400 text-center font-mono">
              ID: {deviceId}
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Tabs */}
          <div className="flex border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2.5 text-xs font-medium transition-colors flex flex-col items-center gap-0.5 ${
                  activeTab === tab.id
                    ? "text-primary-600 border-b-2 border-primary-600"
                    : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                <span className="text-sm">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === "devices" && (
              <div className="space-y-4">
                <DeviceList
                  devices={devices}
                  selectedDeviceId={selectedDeviceId}
                  onSelect={(id) => {
                    setSelectedDeviceId(id);
                    setActiveTab("text");
                  }}
                  onRemove={removeDevice}
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
                      if (verificationDeviceId) setSelectedDeviceId(verificationDeviceId);
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
                  (m) => m.from === selectedDeviceId || m.direction === "sent"
                )}
                selectedDeviceId={selectedDeviceId}
                selectedDeviceName={selectedDevice?.device_name || null}
                onSend={handleSendText}
                disabled={!selectedDeviceId || !selectedDevice?.is_online}
              />
            )}

            {activeTab === "files" && (
              <div className="space-y-4">
                <FileDropZone
                  onFilesSelected={(files) => {
                    if (selectedDeviceId) sendFiles(files, selectedDeviceId);
                  }}
                  disabled={!selectedDeviceId || !selectedDevice?.is_online}
                  maxFileSize={104857600}
                />
                <TransferProgressList
                  transfers={transfers}
                  onCancel={(tid) => {
                    if (selectedDeviceId) cancelTransfer(tid, selectedDeviceId);
                  }}
                  onDownload={(tid) => {
                    const t = transfers.find((x) => x.transferId === tid);
                    if (t) downloadFile(tid, t.fileName);
                  }}
                />
                {!selectedDeviceId && (
                  <p className="text-xs text-gray-400 text-center">
                    Select a device in the Devices tab first
                  </p>
                )}
              </div>
            )}

            {activeTab === "settings" && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold">Connection</h3>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Server</span>
                    <span className="font-mono">{serverUrl}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Device</span>
                    <span>{deviceName}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">ID</span>
                    <span className="font-mono text-gray-400">{deviceId.slice(0, 16)}...</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Paired devices</span>
                    <span>{devices.length}</span>
                  </div>
                </div>

                <h3 className="text-sm font-semibold">Keyboard Shortcuts</h3>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Send text</span>
                    <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-[10px] font-mono">
                      Ctrl+Enter
                    </kbd>
                  </div>
                </div>

                <button
                  onClick={disconnect}
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
