"""WebSocket signaling client — connects to the relay server for pairing and WebRTC negotiation."""

import asyncio
import json
import time
import uuid

import websockets


class SignalingClient:
    def __init__(self, server_url: str, device_name: str, device_id: str | None = None):
        self.server_url = server_url.rstrip("/")
        self.device_name = device_name
        self.device_id = device_id or uuid.uuid4().hex
        self.ws = None
        self._queue: dict[str, asyncio.Queue] = {}
        self._recv_task = None
        self.peer_device_id: str | None = None

    async def connect(self):
        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        if not ws_url.startswith("ws"):
            ws_url = f"ws://{ws_url}"
        url = f"{ws_url}/ws/{self.device_id}?name={self.device_name}"
        self.ws = await websockets.connect(url, max_size=2**20)
        self._recv_task = asyncio.create_task(self._recv_loop())
        print(f"  Connected to relay as '{self.device_name}' ({self.device_id[:8]}...)")

    async def _recv_loop(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")
                if msg_type not in self._queue:
                    self._queue[msg_type] = asyncio.Queue()
                await self._queue[msg_type].put(msg)
        except websockets.ConnectionClosed:
            pass

    async def send(self, msg_type: str, to_device: str | None = None, payload=None):
        msg = {"type": msg_type, "timestamp": time.time()}
        if to_device:
            msg["to_device"] = to_device
        if payload is not None:
            msg["payload"] = payload
        await self.ws.send(json.dumps(msg))

    async def wait_for(self, msg_type: str, timeout: float = 60) -> dict:
        if msg_type not in self._queue:
            self._queue[msg_type] = asyncio.Queue()
        return await asyncio.wait_for(self._queue[msg_type].get(), timeout=timeout)

    async def create_pairing_code(self) -> str:
        await self.send("pair_create")
        msg = await self.wait_for("pair_code", timeout=10)
        code = msg["payload"]["code"]
        return code

    async def join_pairing_code(self, code: str) -> str:
        await self.send("pair_join", payload={"code": code})
        msg = await self.wait_for("pair_accept", timeout=30)
        self.peer_device_id = msg.get("from_device")
        return self.peer_device_id

    async def wait_for_pair(self) -> str:
        msg = await self.wait_for("pair_accept", timeout=120)
        self.peer_device_id = msg.get("from_device")
        return self.peer_device_id

    async def close(self):
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
