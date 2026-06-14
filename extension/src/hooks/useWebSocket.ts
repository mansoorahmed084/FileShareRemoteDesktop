import { useState, useEffect, useCallback } from "react";
import type { ConnectionStatus } from "../lib/types";

export function useConnectionStatus() {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");

  useEffect(() => {
    chrome.runtime.sendMessage({ type: "get_status" }, (res) => {
      if (res?.status) setStatus(res.status);
    });

    const listener = (message: Record<string, unknown>) => {
      if (message.type === "status_changed") {
        setStatus(message.status as ConnectionStatus);
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const connect = useCallback((serverUrl?: string) => {
    chrome.runtime.sendMessage({ type: "connect", serverUrl });
  }, []);

  const disconnect = useCallback(() => {
    chrome.runtime.sendMessage({ type: "disconnect" });
  }, []);

  return { status, connect, disconnect };
}
