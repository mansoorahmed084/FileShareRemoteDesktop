"""Viewer mode — receive WebRTC stream and display with pygame, capture input events."""

import asyncio
import json

import numpy as np
import pygame
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate

from .signaling import SignalingClient


async def run_viewer(
    server_url: str,
    device_name: str,
    code: str,
    enable_input: bool = False,
    enable_clipboard: bool = False,
):
    print("\n=== RemoteDesktop Screen Share — Viewer ===\n")

    signaling = SignalingClient(server_url, device_name)
    await signaling.connect()

    print(f"  Joining with code: {code}")
    peer_id = await signaling.join_pairing_code(code)
    print(f"  Paired with host: {peer_id[:8]}...")

    config = {"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}
    pc = RTCPeerConnection(configuration=config)

    latest_frame: np.ndarray | None = None
    host_width, host_height = 1920, 1080
    dc = None
    clipboard_monitor = None

    if enable_clipboard:
        from .clipboard import ClipboardSync
        clipboard_monitor = ClipboardSync()

    @pc.on("datachannel")
    def on_datachannel(channel):
        nonlocal dc, host_width, host_height
        dc = channel

        @dc.on("message")
        def on_message(data):
            nonlocal host_width, host_height
            try:
                msg = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return
            if msg.get("type") == "host_info":
                host_width = msg.get("width", 1920)
                host_height = msg.get("height", 1080)
                print(f"  Host screen: {host_width}x{host_height}")
            elif msg.get("type") == "clipboard" and clipboard_monitor:
                clipboard_monitor.receive(msg.get("content", ""))

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            asyncio.ensure_future(_receive_frames(track))

    async def _receive_frames(track):
        nonlocal latest_frame
        while True:
            try:
                frame = await track.recv()
                latest_frame = frame.to_ndarray(format="rgb24")
            except Exception:
                break

    @pc.on("connectionstatechange")
    async def on_state_change():
        print(f"  Connection state: {pc.connectionState}")

    print("  Waiting for WebRTC offer...")
    offer_msg = await signaling.wait_for("screen_offer", timeout=30)
    offer_payload = offer_msg["payload"]
    offer = RTCSessionDescription(sdp=offer_payload["sdp"], type=offer_payload["type"])
    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.1)

    await signaling.send("screen_answer", to_device=peer_id, payload={
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    })
    print("  Sent WebRTC answer — connecting...\n")

    ice_task = asyncio.create_task(_handle_remote_ice(signaling, pc))

    while pc.connectionState not in ("connected", "failed", "closed"):
        await asyncio.sleep(0.1)

    if pc.connectionState != "connected":
        print("  WebRTC connection failed.")
        await pc.close()
        await signaling.close()
        return

    print("  Streaming! Press Esc or close window to disconnect.\n")

    pygame.init()
    win_w, win_h = 1280, 720
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption(f"RemoteDesktop — {signaling.device_name}")
    clock = pygame.time.Clock()

    fullscreen = False
    running = True

    try:
        while running and pc.connectionState not in ("failed", "closed"):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    win_w, win_h = event.w, event.h
                    if not fullscreen:
                        screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_F11 or (event.key == pygame.K_f and event.mod & pygame.KMOD_CTRL and event.mod & pygame.KMOD_SHIFT):
                        fullscreen = not fullscreen
                        if fullscreen:
                            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            win_w, win_h = screen.get_size()
                        else:
                            win_w, win_h = 1280, 720
                            screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
                    elif enable_input and dc and dc.readyState == "open":
                        _send_key_event(dc, "key_down", event)
                elif event.type == pygame.KEYUP:
                    if enable_input and dc and dc.readyState == "open":
                        _send_key_event(dc, "key_up", event)
                elif event.type == pygame.MOUSEMOTION:
                    if enable_input and dc and dc.readyState == "open":
                        _send_mouse_move(dc, event.pos, (win_w, win_h))
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if enable_input and dc and dc.readyState == "open":
                        _send_mouse_button(dc, "mouse_down", event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if enable_input and dc and dc.readyState == "open":
                        _send_mouse_button(dc, "mouse_up", event)
                elif event.type in (pygame.MOUSEWHEEL,):
                    if enable_input and dc and dc.readyState == "open":
                        dc.send(json.dumps({
                            "type": "mouse_scroll",
                            "dx": event.x,
                            "dy": event.y,
                        }))

            if latest_frame is not None:
                h, w = latest_frame.shape[:2]
                surface = pygame.image.frombuffer(latest_frame.tobytes(), (w, h), "RGB")
                scaled = pygame.transform.scale(surface, (win_w, win_h))
                screen.blit(scaled, (0, 0))
                pygame.display.flip()

            if enable_clipboard and clipboard_monitor and dc and dc.readyState == "open":
                content = clipboard_monitor.poll_change_sync()
                if content:
                    dc.send(json.dumps({"type": "clipboard", "content": content}))

            clock.tick(60)
            await asyncio.sleep(0.001)

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n  Disconnecting...")
        ice_task.cancel()
        if clipboard_monitor:
            clipboard_monitor.stop()
        pygame.quit()
        await pc.close()
        await signaling.close()
        print("  Done.")


def _send_mouse_move(dc, pos: tuple[int, int], win_size: tuple[int, int]):
    x_norm = pos[0] / win_size[0]
    y_norm = pos[1] / win_size[1]
    dc.send(json.dumps({"type": "mouse_move", "x": x_norm, "y": y_norm}))


def _send_mouse_button(dc, event_type: str, event):
    button_map = {1: "left", 2: "middle", 3: "right"}
    button = button_map.get(event.button, "left")
    dc.send(json.dumps({"type": event_type, "button": button}))


_PYGAME_TO_VK = {
    pygame.K_BACKSPACE: 0x08, pygame.K_TAB: 0x09, pygame.K_RETURN: 0x0D,
    pygame.K_ESCAPE: 0x1B, pygame.K_SPACE: 0x20, pygame.K_DELETE: 0x2E,
    pygame.K_UP: 0x26, pygame.K_DOWN: 0x28, pygame.K_LEFT: 0x25, pygame.K_RIGHT: 0x27,
    pygame.K_HOME: 0x24, pygame.K_END: 0x23, pygame.K_PAGEUP: 0x21, pygame.K_PAGEDOWN: 0x22,
    pygame.K_INSERT: 0x2D, pygame.K_F1: 0x70, pygame.K_F2: 0x71, pygame.K_F3: 0x72,
    pygame.K_F4: 0x73, pygame.K_F5: 0x74, pygame.K_F6: 0x75, pygame.K_F7: 0x76,
    pygame.K_F8: 0x77, pygame.K_F9: 0x78, pygame.K_F10: 0x79, pygame.K_F11: 0x7A,
    pygame.K_F12: 0x7B, pygame.K_LSHIFT: 0xA0, pygame.K_RSHIFT: 0xA1,
    pygame.K_LCTRL: 0xA2, pygame.K_RCTRL: 0xA3, pygame.K_LALT: 0xA4, pygame.K_RALT: 0xA5,
    pygame.K_CAPSLOCK: 0x14, pygame.K_NUMLOCK: 0x90,
}


def _send_key_event(dc, event_type: str, event):
    vk = _PYGAME_TO_VK.get(event.key)
    if vk is None:
        char = event.unicode
        if char and len(char) == 1:
            vk = ord(char.upper())
        else:
            vk = event.key & 0xFF
    mods = []
    if event.mod & pygame.KMOD_CTRL:
        mods.append("ctrl")
    if event.mod & pygame.KMOD_SHIFT:
        mods.append("shift")
    if event.mod & pygame.KMOD_ALT:
        mods.append("alt")
    dc.send(json.dumps({"type": event_type, "vk": vk, "char": event.unicode or "", "modifiers": mods}))


async def _handle_remote_ice(signaling: SignalingClient, pc: RTCPeerConnection):
    try:
        while True:
            msg = await signaling.wait_for("screen_ice", timeout=300)
            candidate_data = msg["payload"]
            candidate = RTCIceCandidate(
                sdpMid=candidate_data.get("sdpMid"),
                sdpMLineIndex=candidate_data.get("sdpMLineIndex"),
                candidate=candidate_data.get("candidate", ""),
            )
            await pc.addIceCandidate(candidate)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
