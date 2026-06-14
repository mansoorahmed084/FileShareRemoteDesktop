export interface WSMessage {
  type: string;
  from_device?: string;
  to_device?: string;
  payload?: Record<string, unknown> | string;
  timestamp?: number;
  nonce?: string;
}

export interface DeviceInfo {
  device_id: string;
  device_name: string;
  is_online: boolean;
}

export interface ExtensionConfig {
  serverUrl: string;
  deviceId: string;
  deviceName: string;
  autoConnect: boolean;
  notifications: boolean;
  theme: "light" | "dark" | "system";
  maxFileSize: number;
}

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

export interface PairedDevice extends DeviceInfo {
  paired_at: number;
}
