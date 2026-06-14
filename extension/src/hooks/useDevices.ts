import { useState, useEffect, useCallback } from "react";
import type { PairedDevice } from "../lib/types";

export function useDevices() {
  const [devices, setDevices] = useState<PairedDevice[]>([]);

  const loadDevices = useCallback(() => {
    chrome.runtime.sendMessage({ type: "get_paired_devices" }, (res) => {
      if (res?.devices) setDevices(res.devices);
    });
  }, []);

  useEffect(() => {
    loadDevices();

    const listener = (message: Record<string, unknown>) => {
      switch (message.type) {
        case "pair_accept":
          loadDevices();
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
              d.device_id === message.device_id ? { ...d, is_online: false } : d
            )
          );
          break;
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, [loadDevices]);

  const removeDevice = useCallback((deviceId: string) => {
    chrome.runtime.sendMessage({ type: "unpair", device_id: deviceId });
    setDevices((prev) => prev.filter((d) => d.device_id !== deviceId));
  }, []);

  return { devices, setDevices, loadDevices, removeDevice };
}
