import json
import logging
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .hub import hub
from .middleware import RateLimitMiddleware, RequestSizeLimitMiddleware
from .models import WSMessage
from .registry import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="RemoteDesktop Relay Server", version="0.1.0")

app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(RequestSizeLimitMiddleware, max_body_size=settings.MAX_MESSAGE_SIZE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "connected_devices": hub.device_count,
        "timestamp": time.time(),
    }


@app.get("/devices")
async def list_devices():
    return {"devices": [d.model_dump() for d in hub.list_devices()]}


@app.websocket("/ws/{device_id}")
async def websocket_endpoint(
    ws: WebSocket,
    device_id: str,
    name: str = Query(default="Unknown Device"),
):
    if hub.device_count >= settings.MAX_CONNECTIONS:
        await ws.close(code=4002, reason="Server full")
        return

    await hub.connect(device_id, name, ws)

    paired = registry.get_paired_devices(device_id)
    for pid in paired:
        if hub.is_online(pid):
            device = hub.get_device(pid)
            await hub.send_to(device_id, {
                "type": "device_online",
                "from_device": pid,
                "payload": {"device_name": device.device_name} if device else {},
            })
            await hub.send_to(pid, {
                "type": "device_online",
                "from_device": device_id,
                "payload": {"device_name": name},
            })

    try:
        while True:
            raw = await ws.receive()

            if raw.get("bytes"):
                await _handle_binary(device_id, raw["bytes"])
                continue

            text = raw.get("text")
            if not text:
                continue

            try:
                data = json.loads(text)
                msg = WSMessage(**data)
            except Exception:
                await hub.send_to(device_id, {
                    "type": "error",
                    "payload": "Invalid message format",
                })
                continue

            await _handle_message(device_id, msg)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error for %s: %s", device_id, e)
    finally:
        paired = registry.get_paired_devices(device_id)
        for pid in paired:
            await hub.send_to(pid, {
                "type": "device_offline",
                "from_device": device_id,
            })
        await hub.disconnect(device_id)


async def _handle_message(device_id: str, msg: WSMessage) -> None:
    match msg.type:
        case "pong":
            pass

        case "pair_create":
            code = registry.create_pairing_code(device_id)
            await hub.send_to(device_id, {
                "type": "pair_code",
                "payload": {"code": code},
            })

        case "pair_join":
            code = msg.payload if isinstance(msg.payload, str) else msg.payload.get("code", "")
            paired_with = registry.redeem_pairing_code(code, device_id)
            if paired_with:
                device_a = hub.get_device(device_id)
                device_b = hub.get_device(paired_with)
                await hub.send_to(device_id, {
                    "type": "pair_accept",
                    "from_device": paired_with,
                    "payload": {"device_name": device_b.device_name} if device_b else {},
                })
                await hub.send_to(paired_with, {
                    "type": "pair_accept",
                    "from_device": device_id,
                    "payload": {"device_name": device_a.device_name} if device_a else {},
                })
            else:
                await hub.send_to(device_id, {
                    "type": "pair_reject",
                    "payload": "Invalid or expired code",
                })

        case "unpair":
            target = msg.to_device
            if target:
                registry.unpair(device_id, target)
                await hub.send_to(device_id, {"type": "unpair_ack", "from_device": target})
                await hub.send_to(target, {"type": "unpair_ack", "from_device": device_id})

        case "restore_pairs":
            device_ids = msg.payload if isinstance(msg.payload, list) else []
            for pid in device_ids:
                if isinstance(pid, str) and pid != device_id:
                    registry.restore_pair(device_id, pid)
            logger.info("Restored %d pairings for %s", len(device_ids), device_id)

        case _:
            if not msg.to_device:
                await hub.send_to(device_id, {
                    "type": "error",
                    "payload": "Missing to_device field",
                })
                return

            if not registry.is_paired(device_id, msg.to_device):
                await hub.send_to(device_id, {
                    "type": "error",
                    "payload": "Not paired with target device",
                })
                return

            relayed = await hub.relay(device_id, msg.to_device, {
                "type": msg.type,
                "from_device": device_id,
                "to_device": msg.to_device,
                "payload": msg.payload,
                "timestamp": msg.timestamp or time.time(),
                "nonce": msg.nonce,
            })
            if not relayed:
                await hub.send_to(device_id, {
                    "type": "error",
                    "payload": "Target device is offline",
                })


async def _handle_binary(device_id: str, data: bytes) -> None:
    if len(data) < 32:
        return
    # Binary header: first 32 bytes contain routing info
    # For now, we use paired devices to determine the target
    paired = registry.get_paired_devices(device_id)
    for pid in paired:
        await hub.send_bytes_to(pid, data)


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-cert", action="store_true", help="Generate self-signed TLS cert and exit")
    args = parser.parse_args()

    if args.generate_cert:
        from generate_cert import generate_self_signed_cert
        generate_self_signed_cert()
    else:
        ssl_kwargs = {}
        if settings.TLS_CERT and settings.TLS_KEY:
            ssl_kwargs["ssl_certfile"] = settings.TLS_CERT
            ssl_kwargs["ssl_keyfile"] = settings.TLS_KEY
            logger.info("TLS enabled: %s", settings.TLS_CERT)

        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=True,
            **ssl_kwargs,
        )
