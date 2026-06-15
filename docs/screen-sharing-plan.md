# Screen Sharing & Remote Control — Design Plan

**Version:** 1.0
**Date:** 2026-06-15
**Status:** Planned

---

## 1. Goal

Bidirectional screen sharing with full remote control (mouse + keyboard) and clipboard sync between two machines. Built as a standalone native Python application — not inside the Chrome extension — for maximum speed and smoothness.

**Key targets:**
- 30–60 FPS screen streaming on LAN
- < 50ms input latency on LAN
- Clipboard copy/paste sync between machines
- Works alongside the existing extension (shared relay server for signaling)
- End-to-end encrypted (reuse existing ECDH + AES-256-GCM model)

---

## 2. Architecture

```
Machine A (Host)                                          Machine B (Viewer)
┌──────────────────────────┐                              ┌──────────────────────────┐
│  screen_share.py         │                              │  screen_share.py         │
│                          │                              │                          │
│  ┌────────────────────┐  │     WebRTC (SRTP/SRTCP)      │  ┌────────────────────┐  │
│  │ Screen Capture     │  │  ◄──────── Video ──────────► │  │ Video Display      │  │
│  │ (dxcam / mss)      │──┼──────────────────────────────┼──│ (pygame / tkinter) │  │
│  └────────────────────┘  │                              │  └────────────────────┘  │
│                          │     WebRTC DataChannel        │                          │
│  ┌────────────────────┐  │  ◄──── Input Events ────────  │  ┌────────────────────┐  │
│  │ Input Injector     │  │  ◄──── Clipboard Sync ──────► │  │ Input Capture      │  │
│  │ (pynput / ctypes)  │◄─┼──────────────────────────────┼──│ (mouse/keyboard    │  │
│  └────────────────────┘  │                              │  │  event listeners)  │  │
│                          │                              │  └────────────────────┘  │
│  ┌────────────────────┐  │     WebSocket (signaling)     │  ┌────────────────────┐  │
│  │ Clipboard Monitor  │  │  ◄─────────────────────────► │  │ Clipboard Monitor  │  │
│  │ (win32clipboard)   │  │   via Relay Server :8765      │  │ (win32clipboard)   │  │
│  └────────────────────┘  │                              │  └────────────────────┘  │
└──────────────────────────┘                              └──────────────────────────┘
                                        │
                              ┌─────────▼─────────┐
                              │   Relay Server     │
                              │   (existing)       │
                              │   WebRTC signaling  │
                              │   + clipboard relay │
                              └────────────────────┘
```

### Why WebRTC?

| Approach | FPS | Latency | Bandwidth | NAT Traversal |
|----------|-----|---------|-----------|---------------|
| WebSocket + JPEG frames | 5–15 | 100–300ms | Very high | Yes (via relay) |
| WebSocket + H.264 chunks | 15–30 | 50–150ms | High | Yes (via relay) |
| **WebRTC (aiortc)** | **30–60** | **20–50ms** | **Adaptive** | **Yes (STUN/TURN)** |
| Raw UDP + custom codec | 60+ | <20ms | Low | No (LAN only) |

WebRTC gives the best balance: hardware-accelerated encoding, adaptive bitrate, built-in packet loss recovery, and NAT traversal for cross-network use. On LAN it goes peer-to-peer (no relay bandwidth cost).

---

## 3. Technology Stack

| Component | Library | Why |
|-----------|---------|-----|
| Screen capture (Windows) | `dxcam` | DXGI Desktop Duplication API — 240fps+, GPU-accelerated, dirty rects |
| Screen capture (fallback) | `mss` | Cross-platform, ~30fps, pure Python |
| Video encoding | `aiortc` (libvpx VP8/VP9) | Built-in to WebRTC, hardware-accelerated where available |
| Transport | `aiortc` | Python WebRTC — SRTP video + DataChannel for input/clipboard |
| Signaling | Existing relay server (WebSocket) | Reuse `/ws/{device_id}` for SDP offer/answer/ICE |
| Input injection (Windows) | `ctypes` + `SendInput` Win32 API | Lowest latency, no extra deps |
| Input injection (cross-platform) | `pynput` | Fallback for macOS/Linux |
| Clipboard (Windows) | `win32clipboard` + `AddClipboardFormatListener` | Native change detection, no polling |
| Clipboard (cross-platform) | `pyperclip` + polling | Simple fallback |
| UI (viewer window) | `pygame` or `tkinter` + canvas | Lightweight, full mouse/keyboard capture |
| UI (controls/config) | `tkinter` or terminal CLI | Session management, quality settings |

### Dependencies (new)

```
aiortc>=1.9.0          # WebRTC (video stream + data channel)
dxcam>=0.4.0           # Windows screen capture (optional, Windows-only)
mss>=9.0.0             # Cross-platform screen capture (fallback)
pynput>=1.7.0          # Mouse/keyboard injection
pygame>=2.5.0          # Viewer window
pyperclip>=1.8.0       # Clipboard (cross-platform fallback)
numpy>=1.26.0          # Frame manipulation
Pillow>=10.0.0         # Image processing
```

Windows-specific (no pip, use ctypes):
- `user32.dll` — `SendInput`, `SetCursorPos`, clipboard monitoring
- `kernel32.dll` — process management

---

## 4. Phased Implementation

### Phase 1: Screen Sharing (View Only) — ~3 days

**Goal:** Stream one machine's screen to the other at 30fps with < 100ms latency.

#### 4.1 Signaling (extend relay server)

Add WebRTC signaling message types to the existing relay:

```python
# New message types handled by the relay (just forwarded between paired devices)
"screen_offer"    # SDP offer from host
"screen_answer"   # SDP answer from viewer
"screen_ice"      # ICE candidate exchange
"screen_request"  # Viewer requests screen share
"screen_stop"     # Either side ends session
```

No server logic needed — just relay these between paired devices (already supported by the default `_` case in `_handle_message`).

#### 4.2 Host: Screen capture + WebRTC stream

```python
# screen/host.py — simplified flow

async def start_sharing(ws_client, peer_device_id):
    # 1. Create WebRTC peer connection
    pc = RTCPeerConnection()
    
    # 2. Add video track (screen capture)
    capture = ScreenCaptureTrack()  # Custom VideoStreamTrack subclass
    pc.addTrack(capture)
    
    # 3. Create and send SDP offer via relay
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    ws_client.send({
        "type": "screen_offer",
        "to_device": peer_device_id,
        "payload": {"sdp": pc.localDescription.sdp, "type": "offer"}
    })
    
    # 4. Wait for answer via relay
    # 5. Exchange ICE candidates
    # 6. Stream starts automatically
```

Screen capture track:

```python
class ScreenCaptureTrack(VideoStreamTrack):
    def __init__(self, fps=30, monitor=0):
        super().__init__()
        self.camera = dxcam.create(output_idx=monitor)
        self.camera.start(target_fps=fps)
    
    async def recv(self):
        frame = self.camera.get_latest_frame()  # numpy array (H, W, 3)
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts, video_frame.time_base = await self.next_timestamp()
        return video_frame
```

#### 4.3 Viewer: Display stream

```python
# screen/viewer.py — simplified flow

async def view_screen(ws_client, peer_device_id):
    pc = RTCPeerConnection()
    
    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            asyncio.ensure_future(display_video(track))
    
    # Wait for offer, set remote description, create answer, send back
    
async def display_video(track):
    """Render frames in a pygame window."""
    pygame.init()
    screen = None
    while True:
        frame = await track.recv()
        img = frame.to_ndarray(format="bgr24")
        if screen is None:
            h, w = img.shape[:2]
            screen = pygame.display.set_mode((w, h))
        surface = pygame.surfarray.make_surface(img.swapaxes(0, 1))
        screen.blit(surface, (0, 0))
        pygame.display.flip()
```

#### 4.4 Deliverable

```bash
# Machine A (host)
python -m screen share --server ws://192.168.0.3:8765 --device-id <id>

# Machine B (viewer)  
python -m screen view --server ws://192.168.0.3:8765 --device-id <id> --target <host-id>
```

Two windows: host shows "Sharing screen..." status, viewer shows real-time stream.

---

### Phase 2: Remote Control (Input) — ~2 days

**Goal:** Viewer can control host's mouse and keyboard with < 50ms latency.

#### 4.5 WebRTC DataChannel for input events

```python
# On host: create data channel
input_channel = pc.createDataChannel("input", ordered=True)

# On viewer: capture and send input events
@input_channel.on("open")
def on_open():
    pass  # Ready to send input

def send_mouse_event(event_type, x, y, button=None, scroll_delta=None):
    """Capture mouse events from pygame viewer and send to host."""
    input_channel.send(json.dumps({
        "type": event_type,  # "mouse_move", "mouse_down", "mouse_up", "mouse_scroll"
        "x": x / viewer_width,   # Normalized 0.0–1.0 (resolution-independent)
        "y": y / viewer_height,
        "button": button,         # "left", "right", "middle"
        "delta": scroll_delta,
    }))

def send_key_event(event_type, key, modifiers):
    """Capture keyboard events and send to host."""
    input_channel.send(json.dumps({
        "type": event_type,  # "key_down", "key_up"
        "key": key,          # Virtual key code
        "modifiers": modifiers,  # ["ctrl", "shift", "alt"]
    }))
```

#### 4.6 Host: Input injection (Windows)

```python
# screen/input_injector.py — Windows via ctypes

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
SM_CXSCREEN = 0
SM_CYSCREEN = 1

def move_mouse(x_norm: float, y_norm: float):
    """Move mouse to normalized coordinates (0.0–1.0)."""
    screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = user32.GetSystemMetrics(SM_CYSCREEN)
    x = int(x_norm * screen_w)
    y = int(y_norm * screen_h)
    user32.SetCursorPos(x, y)

def click(button="left", down=True):
    """Send mouse click via SendInput."""
    # Uses MOUSEINPUT struct with MOUSEEVENTF flags
    ...

def send_key(vk_code: int, down=True):
    """Send keyboard event via SendInput."""
    # Uses KEYBDINPUT struct
    ...
```

Using `SendInput` (Win32) instead of `pyautogui` — it's 10x faster (no Python overhead per event) and works with DirectX/fullscreen apps.

#### 4.7 Coordinate mapping

The viewer window may be a different resolution than the host screen. All coordinates are normalized (0.0–1.0) before sending:

```
Viewer click at (640, 360) in 1280x720 window
  → normalized: (0.5, 0.5)
  → host screen 1920x1080: (960, 540)
```

#### 4.8 Input event batching

Mouse move events fire at 60–120hz. To avoid flooding the data channel:
- Batch mouse moves: send at most every 16ms (60fps)
- Key events: send immediately (latency-sensitive)
- Scroll events: debounce to 50ms

---

### Phase 3: Clipboard Sync — ~1 day

**Goal:** Copy on one machine, paste on the other. Bidirectional.

#### 4.9 Clipboard monitoring (Windows)

```python
# screen/clipboard.py

import win32clipboard
import win32gui
import win32con

class ClipboardMonitor:
    def __init__(self, on_change):
        self.on_change = on_change
        self._last_content = None
        
    def start(self):
        """Create invisible window and register clipboard listener."""
        # Register window class
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "RDClipboardMonitor"
        win32gui.RegisterClass(wc)
        
        # Create invisible window
        self.hwnd = win32gui.CreateWindow(...)
        
        # Listen for clipboard changes (no polling!)
        ctypes.windll.user32.AddClipboardFormatListener(self.hwnd)
    
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_CLIPBOARDUPDATE:
            content = self._read_clipboard()
            if content != self._last_content:
                self._last_content = content
                self.on_change(content)
        return 0
    
    def write(self, text):
        """Write text to clipboard (from remote)."""
        self._last_content = text  # Prevent echo
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
```

#### 4.10 Sync protocol

Clipboard content is sent via the WebRTC DataChannel (encrypted):

```json
{
  "type": "clipboard",
  "format": "text",
  "content": "encrypted_base64_content",
  "nonce": "..."
}
```

- Text clipboard: sync immediately on change (< 1MB)
- Image clipboard: convert to PNG, sync if < 5MB (show notification for larger)
- File clipboard: don't sync (too complex, use the existing file transfer)

#### 4.11 Security

- Clipboard sync is **opt-in** per session (flag: `--clipboard`)
- Content is encrypted with the same AES-256-GCM session key
- Large clipboard content (> 1MB) shows a confirmation dialog before sending

---

### Phase 4: Polish & UX — ~2 days

#### 4.12 Session management

```
# Host starts sharing (prompts for confirmation)
python -m screen share
> Screen sharing session started.
> Waiting for viewer to connect...
> [Viewer "Work Laptop" connected — allow remote control? (y/n)]

# Viewer connects
python -m screen view --target "Home Desktop"
> Connected to "Home Desktop"
> Resolution: 1920x1080 @ 30fps
> Remote control: enabled
> Clipboard sync: enabled
```

Both sides must consent:
1. Host starts sharing → generates session token
2. Viewer requests to connect → host sees confirmation prompt
3. Host approves → WebRTC negotiation begins
4. Either side can disconnect at any time (Esc key or close window)

#### 4.13 Quality controls

| Setting | Default | Range | Notes |
|---------|---------|-------|-------|
| FPS | 30 | 5–60 | Auto-adjusts based on bandwidth |
| Resolution scale | 1.0 | 0.25–1.0 | Downscale before encoding |
| Bitrate | 4 Mbps | 0.5–20 Mbps | Adaptive by default |
| Color depth | Full | Full / Reduced | Reduced = faster encode |

Keyboard shortcuts in viewer:
- `Ctrl+Shift+F` — toggle fullscreen
- `Ctrl+Shift+Q` — disconnect
- `Ctrl+Shift+C` — toggle clipboard sync
- `Ctrl+Shift+Arrow` — switch monitors (multi-monitor host)

#### 4.14 Multi-monitor support

- Host reports available monitors on session start
- Viewer can switch between monitors via shortcut or dropdown
- Default: primary monitor

#### 4.15 Connection quality indicator

Overlay in viewer corner showing:
- FPS (actual)
- Latency (RTT from data channel ping)
- Bandwidth usage
- Packet loss %

---

## 5. Project Structure

```
myRemoteDesktop/
├── screen/                        # NEW — Screen sharing app
│   ├── __init__.py
│   ├── __main__.py                # CLI entry point
│   ├── host.py                    # Screen capture + WebRTC host
│   ├── viewer.py                  # Video display + input capture
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── dxcam_capture.py       # Windows DXGI capture (fast)
│   │   └── mss_capture.py         # Cross-platform fallback
│   ├── input/
│   │   ├── __init__.py
│   │   ├── injector_win32.py      # Windows SendInput via ctypes
│   │   └── injector_pynput.py     # Cross-platform fallback
│   ├── clipboard/
│   │   ├── __init__.py
│   │   ├── monitor_win32.py       # Windows native clipboard listener
│   │   └── monitor_pyperclip.py   # Cross-platform polling fallback
│   ├── signaling.py               # WebSocket signaling via relay server
│   ├── encryption.py              # AES-256-GCM for data channel
│   └── requirements.txt
│
├── server/                        # Existing (no changes needed)
├── extension/                     # Existing (no changes needed)
├── cli/                           # Existing
└── ...
```

---

## 6. CLI Interface

```bash
# Share your screen (host mode)
python -m screen share \
  --server ws://192.168.0.3:8765 \
  --name "Home Desktop" \
  --fps 30 \
  --clipboard \
  --monitor 0

# View and control a remote screen (viewer mode)
python -m screen view \
  --server ws://192.168.0.3:8765 \
  --name "Work Laptop" \
  --target "Home Desktop" \
  --clipboard

# List available devices to connect to
python -m screen devices --server ws://192.168.0.3:8765
```

Or integrated with existing `setup.py`:

```bash
python setup.py --screen-share     # Install screen sharing deps + start host
python setup.py --screen-view      # Install deps + start viewer
```

---

## 7. Security Considerations

| Concern | Mitigation |
|---------|------------|
| Unauthorized screen viewing | Host must explicitly accept each viewer connection |
| Input injection abuse | Remote control requires separate consent toggle |
| Clipboard data leakage | Clipboard sync is opt-in, encrypted, size-limited |
| Man-in-the-middle | Same ECDH + AES-256-GCM as file/text sharing |
| Session hijacking | Session tokens expire on disconnect |
| Screen content exposure | Video stream is SRTP-encrypted (WebRTC default) |

---

## 8. Performance Targets

| Metric | LAN Target | WAN Target |
|--------|-----------|-----------|
| Video FPS | 30–60 | 15–30 |
| Video latency | 20–50ms | 50–150ms |
| Input latency | 10–30ms | 30–80ms |
| Clipboard sync | < 100ms | < 500ms |
| Bandwidth (1080p) | 2–8 Mbps | 1–4 Mbps |
| CPU usage (host) | < 15% | < 15% |
| CPU usage (viewer) | < 10% | < 10% |

---

## 9. Estimated Timeline

| Phase | Scope | Effort |
|-------|-------|--------|
| Phase 1 | Screen streaming (view only) | ~3 days |
| Phase 2 | Remote control (mouse + keyboard) | ~2 days |
| Phase 3 | Clipboard sync | ~1 day |
| Phase 4 | Polish (multi-monitor, quality, UX) | ~2 days |
| **Total** | | **~8 days** |

---

## 10. Dependencies on Existing System

- **Relay server**: Used for WebRTC signaling (SDP/ICE exchange) — no code changes needed, existing message relay handles it
- **Device pairing**: Reuse existing pairing system — only paired devices can request screen sharing
- **Encryption keys**: Reuse ECDH shared keys for data channel encryption
- **Chrome extension**: Independent — screen sharing works without the extension, but can coexist (same server, same device IDs)
