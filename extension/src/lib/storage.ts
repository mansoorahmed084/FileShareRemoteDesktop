import type { ExtensionConfig, PairedDevice } from "./types";

const DEFAULT_CONFIG: ExtensionConfig = {
  serverUrl: "ws://localhost:8765",
  deviceId: "",
  deviceName: "My Device",
  autoConnect: true,
  notifications: true,
  theme: "system",
  maxFileSize: 104857600,
};

function generateDeviceId(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function getConfig(): Promise<ExtensionConfig> {
  const result = await chrome.storage.local.get("config");
  const config = { ...DEFAULT_CONFIG, ...result.config };
  if (!config.deviceId) {
    config.deviceId = generateDeviceId();
    await saveConfig(config);
  }
  return config;
}

export async function saveConfig(config: Partial<ExtensionConfig>): Promise<void> {
  const current = await getConfig();
  await chrome.storage.local.set({ config: { ...current, ...config } });
}

export async function getPairedDevices(): Promise<PairedDevice[]> {
  const result = await chrome.storage.local.get("pairedDevices");
  return result.pairedDevices || [];
}

export async function addPairedDevice(device: PairedDevice): Promise<void> {
  const devices = await getPairedDevices();
  const existing = devices.findIndex((d) => d.device_id === device.device_id);
  if (existing >= 0) {
    devices[existing] = device;
  } else {
    devices.push(device);
  }
  await chrome.storage.local.set({ pairedDevices: devices });
}

export async function removePairedDevice(deviceId: string): Promise<void> {
  const devices = await getPairedDevices();
  await chrome.storage.local.set({
    pairedDevices: devices.filter((d) => d.device_id !== deviceId),
  });
}
