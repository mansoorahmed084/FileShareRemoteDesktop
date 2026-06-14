import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.hub import ConnectionHub


@pytest.fixture
def hub():
    return ConnectionHub()


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_bytes = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_and_disconnect(hub, mock_ws):
    await hub.connect("dev-1", "Test Device", mock_ws)
    assert hub.device_count == 1
    assert hub.is_online("dev-1")

    device = hub.get_device("dev-1")
    assert device is not None
    assert device.device_name == "Test Device"

    await hub.disconnect("dev-1")
    assert hub.device_count == 0
    assert not hub.is_online("dev-1")


@pytest.mark.asyncio
async def test_send_to(hub, mock_ws):
    await hub.connect("dev-1", "Device", mock_ws)
    result = await hub.send_to("dev-1", {"type": "test"})
    assert result is True
    mock_ws.send_text.assert_called_once()
    sent = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent["type"] == "test"


@pytest.mark.asyncio
async def test_send_to_offline_device(hub):
    result = await hub.send_to("nonexistent", {"type": "test"})
    assert result is False


@pytest.mark.asyncio
async def test_relay(hub, mock_ws):
    ws_b = AsyncMock()
    ws_b.accept = AsyncMock()
    ws_b.send_text = AsyncMock()

    await hub.connect("dev-a", "A", mock_ws)
    await hub.connect("dev-b", "B", ws_b)

    result = await hub.relay("dev-a", "dev-b", {"type": "text", "payload": "hello"})
    assert result is True
    ws_b.send_text.assert_called()
    sent = json.loads(ws_b.send_text.call_args[0][0])
    assert sent["from_device"] == "dev-a"


@pytest.mark.asyncio
async def test_list_devices(hub, mock_ws):
    await hub.connect("dev-1", "Device 1", mock_ws)
    devices = hub.list_devices()
    assert len(devices) == 1
    assert devices[0].device_id == "dev-1"


@pytest.mark.asyncio
async def test_replace_existing_connection(hub):
    ws1 = AsyncMock()
    ws1.accept = AsyncMock()
    ws1.close = AsyncMock()
    ws2 = AsyncMock()
    ws2.accept = AsyncMock()
    ws2.send_text = AsyncMock()

    await hub.connect("dev-1", "Device", ws1)
    await hub.connect("dev-1", "Device", ws2)

    assert hub.device_count == 1
    ws1.close.assert_called_once()
