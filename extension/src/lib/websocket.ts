import type { WSMessage, ConnectionStatus } from "./types";

type MessageHandler = (msg: WSMessage) => void;
type StatusHandler = (status: ConnectionStatus) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string = "";
  private deviceId: string = "";
  private deviceName: string = "";
  private reconnectAttempts = 0;
  private maxReconnectDelay = 30000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private messageHandlers: MessageHandler[] = [];
  private statusHandlers: StatusHandler[] = [];
  private _status: ConnectionStatus = "disconnected";

  get status(): ConnectionStatus {
    return this._status;
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.push(handler);
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== handler);
    };
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.push(handler);
    return () => {
      this.statusHandlers = this.statusHandlers.filter((h) => h !== handler);
    };
  }

  connect(url: string, deviceId: string, deviceName: string): void {
    this.url = url;
    this.deviceId = deviceId;
    this.deviceName = deviceName;
    this.reconnectAttempts = 0;
    this._connect();
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this._setStatus("disconnected");
  }

  send(msg: WSMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  sendBinary(data: ArrayBuffer): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(data);
    return true;
  }

  private _connect(): void {
    this._setStatus("connecting");
    const wsUrl = `${this.url}/ws/${this.deviceId}?name=${encodeURIComponent(this.deviceName)}`;

    try {
      this.ws = new WebSocket(wsUrl);
    } catch {
      this._setStatus("error");
      this._scheduleReconnect();
      return;
    }

    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this._setStatus("connected");
    };

    this.ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          if (msg.type === "ping") {
            this.send({ type: "pong", timestamp: Date.now() / 1000 });
            return;
          }
          this.messageHandlers.forEach((h) => h(msg));
        } catch {
          // ignore malformed messages
        }
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      this._setStatus("disconnected");
      this._scheduleReconnect();
    };

    this.ws.onerror = () => {
      this._setStatus("error");
    };
  }

  private _scheduleReconnect(): void {
    const delay = Math.min(
      1000 * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    );
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this._connect();
    }, delay);
  }

  private _setStatus(status: ConnectionStatus): void {
    this._status = status;
    this.statusHandlers.forEach((h) => h(status));
  }
}

export const wsClient = new WebSocketClient();
