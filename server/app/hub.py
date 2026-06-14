import asyncio
import json
import logging
import time

from fastapi import WebSocket

from .models import DeviceInfo

logger = logging.getLogger(__name__)


class ConnectionHub:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._devices: dict[str, DeviceInfo] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    @property
    def device_count(self) -> int:
        return len(self._connections)

    def get_device(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    async def connect(self, device_id: str, device_name: str, ws: WebSocket) -> None:
        await ws.accept()
        if device_id in self._connections:
            old_ws = self._connections[device_id]
            try:
                await old_ws.close(code=4001, reason="Replaced by new connection")
            except Exception:
                pass
            self._cancel_heartbeat(device_id)

        self._connections[device_id] = ws
        self._devices[device_id] = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            connected_at=time.time(),
        )
        self._heartbeat_tasks[device_id] = asyncio.create_task(
            self._heartbeat_loop(device_id)
        )
        logger.info("Device connected: %s (%s)", device_id, device_name)

    async def disconnect(self, device_id: str) -> None:
        self._connections.pop(device_id, None)
        self._devices.pop(device_id, None)
        self._cancel_heartbeat(device_id)
        logger.info("Device disconnected: %s", device_id)

    async def send_to(self, device_id: str, message: dict) -> bool:
        ws = self._connections.get(device_id)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception:
            await self.disconnect(device_id)
            return False

    async def send_bytes_to(self, device_id: str, data: bytes) -> bool:
        ws = self._connections.get(device_id)
        if not ws:
            return False
        try:
            await ws.send_bytes(data)
            return True
        except Exception:
            await self.disconnect(device_id)
            return False

    async def relay(self, from_id: str, to_id: str, message: dict) -> bool:
        message["from_device"] = from_id
        return await self.send_to(to_id, message)

    def is_online(self, device_id: str) -> bool:
        return device_id in self._connections

    def _cancel_heartbeat(self, device_id: str) -> None:
        task = self._heartbeat_tasks.pop(device_id, None)
        if task:
            task.cancel()

    async def _heartbeat_loop(self, device_id: str) -> None:
        from .config import settings

        try:
            while device_id in self._connections:
                await asyncio.sleep(settings.HEARTBEAT_INTERVAL)
                sent = await self.send_to(
                    device_id, {"type": "ping", "timestamp": time.time()}
                )
                if not sent:
                    break
        except asyncio.CancelledError:
            pass


hub = ConnectionHub()
