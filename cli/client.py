"""Shared WebSocket client for CLI and MCP server."""

import asyncio
import json
import hashlib
import os
import time
import uuid
import base64
from pathlib import Path
from dataclasses import dataclass, field

import websockets
from websockets.asyncio.client import ClientConnection


@dataclass
class DeviceInfo:
    device_id: str
    device_name: str
    is_online: bool = False


@dataclass
class ReceivedMessage:
    id: str
    from_device: str
    text: str
    timestamp: float


@dataclass
class ReceivedFile:
    id: str
    from_device: str
    file_name: str
    file_size: int
    data: bytes
    timestamp: float


@dataclass
class ClientState:
    device_id: str = ""
    device_name: str = ""
    server_url: str = ""
    connected: bool = False
    paired_devices: dict[str, DeviceInfo] = field(default_factory=dict)
    messages: list[ReceivedMessage] = field(default_factory=list)
    received_files: list[ReceivedFile] = field(default_factory=list)
    pairing_code: str | None = None
    _pending_chunks: dict[str, dict] = field(default_factory=dict)


CHUNK_SIZE = 64 * 1024
CONFIG_DIR = Path.home() / ".remote-desktop"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_or_create_device_id() -> str:
    config = load_config()
    if "device_id" not in config:
        config["device_id"] = uuid.uuid4().hex
        save_config(config)
    return config["device_id"]


class RemoteDesktopClient:
    def __init__(self) -> None:
        self.state = ClientState()
        self._ws: ClientConnection | None = None
        self._listener_task: asyncio.Task | None = None
        self._callbacks: dict[str, list] = {}

    def on(self, event: str, callback) -> None:
        self._callbacks.setdefault(event, []).append(callback)

    def _emit(self, event: str, data=None) -> None:
        for cb in self._callbacks.get(event, []):
            if asyncio.iscoroutinefunction(cb):
                asyncio.create_task(cb(data))
            else:
                cb(data)

    async def connect(self, server_url: str, device_name: str = "CLI Device") -> None:
        self.state.device_id = get_or_create_device_id()
        self.state.device_name = device_name
        self.state.server_url = server_url

        ws_url = f"{server_url}/ws/{self.state.device_id}?name={device_name}"
        self._ws = await websockets.connect(ws_url)
        self.state.connected = True
        self._listener_task = asyncio.create_task(self._listen())

        config = load_config()
        config["server_url"] = server_url
        config["device_name"] = device_name
        save_config(config)

        self._emit("connected")

    async def disconnect(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            self._listener_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
        self.state.connected = False
        self._emit("disconnected")

    async def pair_create(self) -> str:
        await self._send({"type": "pair_create"})
        for _ in range(100):
            await asyncio.sleep(0.1)
            if self.state.pairing_code:
                code = self.state.pairing_code
                self.state.pairing_code = None
                return code
        raise TimeoutError("No pairing code received")

    async def pair_join(self, code: str) -> str | None:
        await self._send({"type": "pair_join", "payload": {"code": code}})
        for _ in range(100):
            await asyncio.sleep(0.1)
            if len(self.state.paired_devices) > 0:
                return list(self.state.paired_devices.keys())[-1]
        return None

    async def send_text(self, to_device: str, text: str) -> bool:
        return await self._send({
            "type": "text",
            "from_device": self.state.device_id,
            "to_device": to_device,
            "payload": {"text": text},
            "timestamp": time.time(),
        })

    async def send_file(self, to_device: str, file_path: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = path.read_bytes()
        file_size = len(data)
        sha256 = hashlib.sha256(data).hexdigest()
        transfer_id = uuid.uuid4().hex
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        await self._send({
            "type": "file_meta",
            "from_device": self.state.device_id,
            "to_device": to_device,
            "payload": {
                "transferId": transfer_id,
                "fileName": path.name,
                "fileSize": file_size,
                "fileType": "application/octet-stream",
                "totalChunks": total_chunks,
                "sha256": sha256,
            },
            "timestamp": time.time(),
        })

        for i in range(total_chunks):
            start = i * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, file_size)
            chunk = data[start:end]
            chunk_b64 = base64.b64encode(chunk).decode()

            await self._send({
                "type": "file_chunk",
                "from_device": self.state.device_id,
                "to_device": to_device,
                "payload": {
                    "transferId": transfer_id,
                    "index": i,
                    "total": total_chunks,
                    "data": chunk_b64,
                    "nonce": "",
                },
                "timestamp": time.time(),
            })

            self._emit("file_progress", {
                "transfer_id": transfer_id,
                "chunk": i + 1,
                "total": total_chunks,
                "file_name": path.name,
            })

        return True

    def get_messages(self, limit: int = 50) -> list[ReceivedMessage]:
        return self.state.messages[-limit:]

    def get_received_files(self) -> list[ReceivedFile]:
        return list(self.state.received_files)

    def save_received_file(self, file_id: str, dest_path: str) -> str:
        for f in self.state.received_files:
            if f.id == file_id:
                path = Path(dest_path)
                if path.is_dir():
                    path = path / f.file_name
                path.write_bytes(f.data)
                return str(path)
        raise ValueError(f"No received file with id: {file_id}")

    def list_devices(self) -> list[DeviceInfo]:
        return list(self.state.paired_devices.values())

    async def _send(self, msg: dict) -> bool:
        if not self._ws:
            return False
        await self._ws.send(json.dumps(msg))
        return True

    async def _listen(self) -> None:
        try:
            async for raw in self._ws:
                if isinstance(raw, str):
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    await self._handle(msg)
        except websockets.ConnectionClosed:
            self.state.connected = False
            self._emit("disconnected")
        except asyncio.CancelledError:
            pass

    async def _handle(self, msg: dict) -> None:
        msg_type = msg.get("type", "")

        match msg_type:
            case "ping":
                await self._send({"type": "pong", "timestamp": time.time()})

            case "pair_code":
                payload = msg.get("payload", {})
                self.state.pairing_code = payload.get("code")
                self._emit("pair_code", self.state.pairing_code)

            case "pair_accept":
                from_device = msg.get("from_device", "")
                payload = msg.get("payload", {})
                name = payload.get("device_name", "Unknown")
                self.state.paired_devices[from_device] = DeviceInfo(
                    device_id=from_device, device_name=name, is_online=True
                )
                self._emit("pair_accept", from_device)

            case "pair_reject":
                self._emit("pair_reject", msg.get("payload"))

            case "device_online":
                did = msg.get("from_device", "")
                payload = msg.get("payload", {})
                name = payload.get("device_name", "Unknown") if isinstance(payload, dict) else "Unknown"
                if did in self.state.paired_devices:
                    self.state.paired_devices[did].is_online = True
                else:
                    self.state.paired_devices[did] = DeviceInfo(
                        device_id=did, device_name=name, is_online=True
                    )
                self._emit("device_online", did)

            case "device_offline":
                did = msg.get("from_device", "")
                if did in self.state.paired_devices:
                    self.state.paired_devices[did].is_online = False
                self._emit("device_offline", did)

            case "text":
                payload = msg.get("payload", {})
                text = payload.get("text", "") if isinstance(payload, dict) else str(payload)
                rm = ReceivedMessage(
                    id=uuid.uuid4().hex,
                    from_device=msg.get("from_device", ""),
                    text=text,
                    timestamp=msg.get("timestamp", time.time()),
                )
                self.state.messages.append(rm)
                self._emit("text", rm)

            case "file_meta":
                payload = msg.get("payload", {})
                tid = payload.get("transferId", "")
                self.state._pending_chunks[tid] = {
                    "meta": payload,
                    "chunks": {},
                }
                await self._send({
                    "type": "file_ack",
                    "from_device": self.state.device_id,
                    "to_device": msg.get("from_device", ""),
                    "payload": {"transferId": tid, "status": "ready"},
                })
                self._emit("file_incoming", payload)

            case "file_chunk":
                payload = msg.get("payload", {})
                tid = payload.get("transferId", "")
                pending = self.state._pending_chunks.get(tid)
                if not pending:
                    return

                idx = payload.get("index", 0)
                chunk_data = base64.b64decode(payload.get("data", ""))
                pending["chunks"][idx] = chunk_data

                meta = pending["meta"]
                total = meta.get("totalChunks", 1)

                self._emit("file_progress", {
                    "transfer_id": tid,
                    "chunk": len(pending["chunks"]),
                    "total": total,
                    "file_name": meta.get("fileName", ""),
                })

                if len(pending["chunks"]) == total:
                    parts = []
                    for i in range(total):
                        parts.append(pending["chunks"][i])
                    assembled = b"".join(parts)

                    rf = ReceivedFile(
                        id=tid,
                        from_device=msg.get("from_device", ""),
                        file_name=meta.get("fileName", "file"),
                        file_size=len(assembled),
                        data=assembled,
                        timestamp=time.time(),
                    )
                    self.state.received_files.append(rf)
                    del self.state._pending_chunks[tid]
                    self._emit("file_complete", rf)

            case "error":
                self._emit("error", msg.get("payload"))
