"""Host mode — capture screen and stream via WebRTC."""

import asyncio
import fractions
import time

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate
from av import VideoFrame

from .capture import create_capture, grab_async
from .signaling import SignalingClient

VIDEO_CLOCK_RATE = 90000


class ScreenCaptureTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, capture, fps: int = 30):
        super().__init__()
        self._capture = capture
        self._fps = fps
        self._ptime = 1 / fps
        self._start: float | None = None
        self._timestamp = 0

    async def recv(self):
        if self._start is None:
            self._start = time.time()
        else:
            self._timestamp += int(self._ptime * VIDEO_CLOCK_RATE)
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            if wait > 0:
                await asyncio.sleep(wait)

        frame = await grab_async(self._capture)
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = self._timestamp
        video_frame.time_base = fractions.Fraction(1, VIDEO_CLOCK_RATE)
        return video_frame


async def run_host(
    server_url: str,
    device_name: str,
    fps: int = 30,
    monitor: int = 0,
    enable_input: bool = False,
    enable_clipboard: bool = False,
):
    print("\n=== RemoteDesktop Screen Share — Host ===\n")

    capture = create_capture(monitor)
    signaling = SignalingClient(server_url, device_name)
    await signaling.connect()

    code = await signaling.create_pairing_code()
    print(f"\n  Pairing code: {code}")
    print("  Waiting for viewer to connect...\n")

    peer_id = await signaling.wait_for_pair()
    print(f"  Viewer connected: {peer_id[:8]}...")

    config = {"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}
    pc = RTCPeerConnection(configuration=config)

    video_track = ScreenCaptureTrack(capture, fps=fps)
    pc.addTrack(video_track)

    dc = pc.createDataChannel("control", ordered=True)
    input_injector = None
    clipboard_monitor = None

    if enable_input:
        from .input_injector import create_injector
        input_injector = create_injector(capture.width, capture.height)
        print("  Remote input: enabled")

    if enable_clipboard:
        from .clipboard import ClipboardSync
        clipboard_monitor = ClipboardSync()

    @dc.on("open")
    def on_dc_open():
        print("  Data channel open — control ready")
        dc.send('{"type":"host_info","width":%d,"height":%d}' % (capture.width, capture.height))
        if enable_clipboard and clipboard_monitor:
            asyncio.ensure_future(_clipboard_send_loop(dc, clipboard_monitor))

    @dc.on("message")
    def on_dc_message(data):
        import json
        try:
            msg = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return
        msg_type = msg.get("type", "")
        if input_injector and msg_type in ("mouse_move", "mouse_down", "mouse_up", "mouse_scroll", "key_down", "key_up"):
            input_injector.handle(msg)
        elif enable_clipboard and clipboard_monitor and msg_type == "clipboard":
            clipboard_monitor.receive(msg.get("content", ""))

    @pc.on("connectionstatechange")
    async def on_state_change():
        print(f"  Connection state: {pc.connectionState}")
        if pc.connectionState in ("failed", "closed"):
            print("  Viewer disconnected.")

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.1)

    await signaling.send("screen_offer", to_device=peer_id, payload={
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    })
    print("  Sent WebRTC offer, waiting for answer...")

    answer_msg = await signaling.wait_for("screen_answer", timeout=30)
    answer_payload = answer_msg["payload"]
    answer = RTCSessionDescription(sdp=answer_payload["sdp"], type=answer_payload["type"])
    await pc.setRemoteDescription(answer)
    print("  WebRTC connected — streaming screen\n")

    ice_task = asyncio.create_task(_handle_remote_ice(signaling, pc))

    print("  Press Ctrl+C to stop sharing.\n")
    try:
        while pc.connectionState not in ("failed", "closed"):
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n  Stopping...")
        ice_task.cancel()
        if clipboard_monitor:
            clipboard_monitor.stop()
        capture.close()
        await pc.close()
        await signaling.close()
        print("  Done.")


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


async def _clipboard_send_loop(dc, clipboard_monitor):
    while True:
        content = await clipboard_monitor.poll_change()
        if content and dc.readyState == "open":
            import json
            dc.send(json.dumps({"type": "clipboard", "content": content}))
        await asyncio.sleep(0.5)
