# RemoteDesktop — Secure Device Bridge

## Design Document

**Version:** 1.0
**Date:** 2025-06-15
**Author:** Product Architecture
**Status:** Draft

---

## 1. Vision

A Chrome extension + self-hosted relay server that lets you share files and text between your devices instantly and securely over WebSockets. Built for developers who work across multiple machines and need to move env variables, config snippets, and files without email/cloud/USB friction.

**Core Principles:**
- Zero cost — self-hosted, no cloud services required
- Zero trust — server never sees plaintext, E2E encrypted
- Zero friction — pair once, share with one click
- Dev-first — optimized for `.env` files, code snippets, config sharing

---

## 2. Architecture

### 2.1 System Diagram

```
┌─────────────────────┐         ┌──────────────────┐         ┌─────────────────────┐
│   Device A          │         │   Relay Server    │         │   Device B          │
│   Chrome Extension  │         │   (Python/FastAPI)│         │   Chrome Extension  │
│                     │         │                   │         │                     │
│  ┌───────────────┐  │  WSS    │  ┌─────────────┐  │  WSS    │  ┌───────────────┐  │
│  │ Service Worker│──┼────────►│  │  WebSocket  │  │◄────────┼──│ Service Worker│  │
│  │ (background)  │  │         │  │  Hub        │  │         │  │ (background)  │  │
│  └───────┬───────┘  │         │  └──────┬──────┘  │         │  └───────┬───────┘  │
│          │          │         │         │         │         │          │          │
│  ┌───────▼───────┐  │         │  ┌──────▼──────┐  │         │  ┌───────▼───────┐  │
│  │ Popup UI      │  │         │  │ Device      │  │         │  │ Popup UI      │  │
│  │ (React)       │  │         │  │ Registry    │  │         │  │ (React)       │  │
│  └───────────────┘  │         │  └─────────────┘  │         │  └───────────────┘  │
│                     │         │                   │         │                     │
│  ┌───────────────┐  │         │  No data stored.  │         │  ┌───────────────┐  │
│  │ Side Panel    │  │         │  No decryption.   │         │  │ Side Panel    │  │
│  │ (React)       │  │         │  Relay only.      │         │  │ (React)       │  │
│  └───────────────┘  │         │                   │         │  └───────────────┘  │
└─────────────────────┘         └──────────────────┘         └─────────────────────┘
```

### 2.2 Component Overview

| Component | Tech | Role |
|-----------|------|------|
| Relay Server | Python 3.12, FastAPI, uvicorn | Device registry, WebSocket message relay |
| Chrome Extension | TypeScript, React 18, Vite, Tailwind | UI, crypto, file chunking, WS client |
| Native Messaging Host | Python, Chrome Native Messaging | Start/stop server from extension with one click |
| Encryption | Web Crypto API (browser), `cryptography` (server) | E2E encryption, key exchange |

### 2.3 Communication Protocol

All messages use a JSON envelope:

```json
{
  "type": "text|file_meta|file_chunk|file_ack|pair_request|pair_accept|key_exchange|ping|pong",
  "from": "device_id",
  "to": "device_id",
  "payload": "...",
  "timestamp": 1718400000,
  "nonce": "base64_nonce"
}
```

Binary file chunks are sent as binary WebSocket frames with a 32-byte header:
- Bytes 0-15: transfer ID (UUID)
- Bytes 16-19: chunk index (uint32 big-endian)
- Bytes 20-23: total chunks (uint32 big-endian)
- Bytes 24-31: reserved
- Bytes 32+: encrypted chunk data

### 2.4 Native Messaging Host (One-Click Server)

The extension can start/stop the relay server without a terminal via Chrome's Native Messaging API.

```
┌──────────────────────┐     stdin/stdout     ┌──────────────────────┐
│  Chrome Extension    │  (4-byte length +    │  native_host.py      │
│  Service Worker      │   JSON messages)     │  (short-lived)       │
│                      │◄────────────────────►│                      │
│  chrome.runtime      │                      │  Reads command,      │
│  .connectNative()    │                      │  spawns/kills server │
└──────────────────────┘                      └───────┬──────────────┘
                                                      │
                                              ┌───────▼──────────────┐
                                              │  uvicorn relay       │
                                              │  (detached process)  │
                                              │  Survives host exit  │
                                              │  PID → .server.pid   │
                                              └──────────────────────┘
```

**How it works:**

1. The extension sends a `start_server` command via `chrome.runtime.connectNative()`
2. `native_host.py` spawns uvicorn as a **detached process** (`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` on Windows, `start_new_session=True` on Unix)
3. The server process outlives the native host — Chrome kills the host when the service worker sleeps, but the server keeps running
4. PID is stored in `server/.server.pid` for later stop commands
5. The host polls `http://localhost:<port>/health` to confirm startup before responding

**Message protocol:** Chrome Native Messaging uses 4-byte little-endian length prefix followed by UTF-8 JSON. Commands: `start_server`, `stop_server`, `server_status`, `ping`.

**Registration:** `python setup.py --native-host <extension-id>` writes a manifest JSON and registers it in the Windows registry at `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.remotedesktop.relay`.

---

## 3. Security Architecture

### 3.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Server compromise | E2E encryption — server only relays opaque blobs |
| Man-in-the-middle | TLS (WSS) + X25519 key exchange with visual verification |
| Replay attacks | Per-message nonce + timestamp validation (5-minute window) |
| Device impersonation | HMAC-based device tokens + pairing codes |
| Unauthorized access | 6-digit pairing code, expires in 60 seconds |
| Data at rest | Nothing stored on server; extension uses `chrome.storage.session` (memory-only) |

### 3.2 Encryption Flow

```
Device A                                              Device B
   │                                                     │
   ├── Generate X25519 keypair (ephemeral) ──────────────┤
   │                                                     ├── Generate X25519 keypair (ephemeral)
   ├── Send public key via relay ────────────────────────►│
   │◄──────────────────────────── Send public key via relay┤
   │                                                     │
   ├── ECDH shared secret = X25519(privA, pubB)          ├── ECDH shared secret = X25519(privB, pubA)
   ├── Derive AES key = HKDF-SHA256(shared, salt, info)  ├── Derive AES key = HKDF-SHA256(shared, salt, info)
   │                                                     │
   ├── Encrypt(AES-256-GCM, key, nonce, plaintext) ─────►│
   │                                                     ├── Decrypt(AES-256-GCM, key, nonce, ciphertext)
```

### 3.3 Device Pairing

1. Device A opens extension, clicks "Pair New Device"
2. Server generates 6-digit code, associates with Device A's ID, starts 60s timer
3. Device B opens extension, enters the 6-digit code
4. Server verifies code, connects the two devices
5. Devices perform X25519 key exchange through the relay
6. Both devices display a 4-emoji verification string derived from the shared secret
7. User visually confirms emojis match on both screens
8. Pairing is complete; shared secret is stored in `chrome.storage.local` (encrypted by Chrome)

---

## 4. Project Structure

```
myRemoteDesktop/
├── docs/
│   └── design.md                    # This file
│
├── server/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app, WebSocket endpoint
│   │   ├── config.py                # Settings (host, port, TLS paths)
│   │   ├── models.py                # Pydantic message schemas
│   │   ├── hub.py                   # WebSocket connection manager
│   │   ├── registry.py              # Device registry + pairing logic
│   │   └── middleware.py            # Rate limiting, request validation
│   ├── tests/
│   │   ├── test_hub.py
│   │   ├── test_registry.py
│   │   └── test_integration.py
│   ├── native_host.py               # Chrome native messaging host (start/stop server)
│   ├── start_host.bat               # Windows batch wrapper for native host
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── extension/
│   ├── public/
│   │   ├── icons/                   # Extension icons (16, 48, 128)
│   │   └── manifest.json            # Chrome MV3 manifest
│   ├── src/
│   │   ├── background/
│   │   │   └── service-worker.ts    # WS connection, message router
│   │   ├── popup/
│   │   │   ├── App.tsx              # Quick share popup
│   │   │   ├── main.tsx             # React mount
│   │   │   └── index.html
│   │   ├── sidepanel/
│   │   │   ├── App.tsx              # Full dashboard
│   │   │   ├── main.tsx
│   │   │   └── index.html
│   │   ├── lib/
│   │   │   ├── crypto.ts            # X25519, AES-256-GCM, HKDF
│   │   │   ├── websocket.ts         # WSS client, reconnect, heartbeat
│   │   │   ├── file-transfer.ts     # Chunked send/receive, progress
│   │   │   ├── storage.ts           # chrome.storage helpers
│   │   │   └── types.ts             # Shared types
│   │   ├── components/
│   │   │   ├── DeviceList.tsx        # Online/offline device cards
│   │   │   ├── FileDropZone.tsx      # Drag-and-drop file area
│   │   │   ├── TextShare.tsx         # Text/env input + send
│   │   │   ├── PairingDialog.tsx     # Pair code display/entry
│   │   │   ├── TransferProgress.tsx  # File transfer progress bar
│   │   │   └── StatusBadge.tsx       # Connection status indicator
│   │   └── hooks/
│   │       ├── useWebSocket.ts       # WS connection hook
│   │       ├── useDevices.ts         # Device list state
│   │       └── useFileTransfer.ts    # File transfer state
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── README.md
│
├── .gitignore
└── README.md
```

---

## 5. Phased Implementation Plan

### Phase 1: Foundation (Server + Extension Shell)

**Goal:** Working WebSocket connection between two Chrome extensions through a relay server.

**Server tasks:**
- [ ] Initialize Python project with FastAPI + uvicorn
- [ ] Implement WebSocket endpoint (`/ws/{device_id}`)
- [ ] Build connection manager (hub) — track connected devices, route messages
- [ ] Add device registration — assign device ID on first connect, persist in memory
- [ ] Add health check endpoint (`GET /health`)
- [ ] Add CORS configuration for chrome-extension:// origins
- [ ] Write unit tests for hub and registry

**Extension tasks:**
- [ ] Scaffold Vite + React + TypeScript project
- [ ] Create Manifest V3 with permissions: `storage`, `sidePanel`, `activeTab`
- [ ] Implement service worker with WebSocket client (connect, reconnect, heartbeat)
- [ ] Build minimal popup UI — connection status indicator, server URL input
- [ ] Store server URL and device ID in `chrome.storage.local`

**Deliverable:** Two Chrome instances connect to the relay server. Each sees the other as "online." Messages can be echoed between them (plaintext, no encryption yet).

**Estimated effort:** 2-3 days

---

### Phase 2: Device Pairing + Text Sharing

**Goal:** Secure device pairing and encrypted text transfer.

**Server tasks:**
- [ ] Implement pairing code generation (`POST /pair/create` → 6-digit code)
- [ ] Implement pairing code redemption (`POST /pair/join` → device linking)
- [ ] Add pairing expiry (60 seconds) with cleanup
- [ ] Route messages only between paired devices (reject unpaired)
- [ ] Add rate limiting on pairing attempts (max 5 per minute per IP)

**Extension tasks (crypto):**
- [ ] Implement X25519 key pair generation using Web Crypto API
- [ ] Implement ECDH shared secret derivation
- [ ] Implement HKDF-SHA256 key derivation (shared secret → AES key)
- [ ] Implement AES-256-GCM encrypt/decrypt
- [ ] Generate 4-emoji verification string from shared secret

**Extension tasks (UI):**
- [ ] Build PairingDialog — display code, enter code, show emoji verification
- [ ] Build DeviceList — show paired devices with online/offline status
- [ ] Build TextShare — textarea input, "Send" button, received text display
- [ ] Add clipboard integration — "Copy to Clipboard" on received text
- [ ] Add `.env` format detection — syntax highlighting for env variables
- [ ] Chrome notifications on received text

**Deliverable:** Two devices can pair securely, exchange encrypted text messages, and share clipboard content. Env variables can be sent and auto-copied.

**Estimated effort:** 3-4 days

---

### Phase 3: File Transfer

**Goal:** Encrypted file sharing with progress indication, up to 100MB.

**Server tasks:**
- [ ] Handle binary WebSocket frames (relay without parsing)
- [ ] Add transfer session tracking (for progress queries)
- [ ] Implement backpressure — pause relay if receiver is slow
- [ ] Add max file size validation (configurable, default 100MB)

**Extension tasks (core):**
- [ ] Implement file chunking — read File as ArrayBuffer, split into 64KB chunks
- [ ] Implement chunk encryption — AES-256-GCM per chunk with sequential nonce
- [ ] Build binary frame protocol (32-byte header + encrypted payload)
- [ ] Implement chunk reassembly on receiver side
- [ ] Implement integrity check — SHA-256 hash of complete file, verified after reassembly
- [ ] Handle transfer cancellation (sender or receiver)
- [ ] Handle chunk retransmission on failure

**Extension tasks (UI):**
- [ ] Build FileDropZone — drag-and-drop area with file type icons
- [ ] Build TransferProgress — per-file progress bar, speed, ETA
- [ ] Add file browser button as alternative to drag-drop
- [ ] Add received files list with download buttons
- [ ] Chrome notifications on file received

**File transfer flow:**
```
Sender                          Relay                         Receiver
  │                               │                              │
  ├── file_meta (name, size,      │                              │
  │    hash, total_chunks) ──────►├─────────────────────────────►│
  │                               │                              ├── file_ack (ready)
  │◄──────────────────────────────┤◄─────────────────────────────┤
  │                               │                              │
  ├── chunk[0] (binary) ─────────►├─────────────────────────────►│
  ├── chunk[1] (binary) ─────────►├─────────────────────────────►│
  │   ...                         │                              │
  ├── chunk[N] (binary) ─────────►├─────────────────────────────►│
  │                               │                              │
  │                               │                              ├── file_complete
  │◄──────────────────────────────┤◄─────────────────────────────┤   (hash verified)
```

**Deliverable:** Files up to 100MB can be shared between paired devices with encryption, progress tracking, and integrity verification.

**Estimated effort:** 3-4 days

---

### Phase 4: Side Panel Dashboard + UX Polish

**Goal:** Full-featured side panel UI with history, multi-device management, and polished UX.

**Extension tasks (side panel):**
- [ ] Build side panel layout — tabs for Devices, Text, Files, Settings
- [ ] Devices tab — list paired devices, add/remove, online status, last seen
- [ ] Text tab — conversation-style view of sent/received text, search
- [ ] Files tab — transfer history, re-download received files, file previews
- [ ] Settings tab — server URL, device name, auto-connect toggle, theme

**Extension tasks (UX):**
- [ ] Add keyboard shortcuts (Ctrl+Shift+V to send clipboard)
- [ ] Add context menu integration — right-click text → "Send to Device"
- [ ] Add badge on extension icon showing unread count
- [ ] Add connection status in popup (connected/reconnecting/disconnected)
- [ ] Add dark mode support
- [ ] Toast notifications for send/receive confirmations
- [ ] Responsive layout for different popup/sidepanel sizes

**Extension tasks (reliability):**
- [ ] WebSocket auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)
- [ ] Offline queue — messages sent while disconnected are queued and sent on reconnect
- [ ] Transfer resume — interrupted file transfers resume from last acknowledged chunk

**Deliverable:** Polished, full-featured Chrome extension with side panel dashboard, keyboard shortcuts, and reliable connectivity.

**Estimated effort:** 3-4 days

---

### Phase 5: Security Hardening + Production Readiness

**Goal:** Harden security, add TLS, containerize, write documentation.

**Server tasks:**
- [ ] Add TLS support (self-signed cert generation script for local use)
- [ ] Add `--generate-cert` CLI flag for easy setup
- [ ] Implement connection rate limiting (max 10 connections per IP)
- [ ] Implement message rate limiting (max 100 messages per minute per device)
- [ ] Add request size limits (reject messages > 128KB, binary > 64KB + header)
- [ ] Add logging with structured JSON output
- [ ] Create Dockerfile with multi-stage build
- [ ] Create docker-compose.yml with TLS volume mounts
- [ ] Write server README with setup instructions

**Extension tasks:**
- [ ] Enforce WSS-only connections (reject ws://)
- [ ] Add certificate pinning for self-signed certs (store cert hash)
- [ ] Validate all incoming message schemas before processing
- [ ] Add CSP headers to extension HTML pages
- [ ] Sanitize all displayed text (prevent XSS in received messages)
- [ ] Clear sensitive data from memory after use (key material)
- [ ] Session key rotation — new keys every 24 hours or on demand

**Testing:**
- [ ] Integration tests — full pair → encrypt → send → decrypt flow
- [ ] Load test — 10 simultaneous file transfers
- [ ] Security test — attempt message injection, replay, impersonation
- [ ] Cross-platform test — Windows ↔ Windows, Windows ↔ Mac, Windows ↔ Linux

**Documentation:**
- [ ] Write user-facing README with setup guide
- [ ] Document security model and threat analysis
- [ ] Add troubleshooting guide (firewall, cert issues, reconnection)

**Deliverable:** Production-ready, secure, containerized application with full documentation.

**Estimated effort:** 3-4 days

---

## 6. API Reference

### 6.1 REST Endpoints (Server)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server health check |
| `GET` | `/devices` | List connected devices (requires device token) |
| `POST` | `/pair/create` | Generate 6-digit pairing code |
| `POST` | `/pair/join` | Redeem pairing code |
| `DELETE` | `/pair/{device_id}` | Unpair a device |
| `WebSocket` | `/ws/{device_id}` | Main WebSocket connection |

### 6.2 WebSocket Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `register` | Client → Server | Register device with name and token |
| `pair_request` | Client → Server | Request pairing with code |
| `pair_accept` | Server → Client | Pairing confirmed |
| `key_exchange` | Client ↔ Client | X25519 public key exchange |
| `text` | Client ↔ Client | Encrypted text message |
| `file_meta` | Client → Client | File metadata before transfer |
| `file_chunk` | Client → Client | Binary encrypted file chunk |
| `file_ack` | Client → Client | Chunk/file acknowledgment |
| `file_cancel` | Client → Client | Cancel ongoing transfer |
| `device_online` | Server → Client | Paired device came online |
| `device_offline` | Server → Client | Paired device went offline |
| `ping` / `pong` | Both | Keepalive (every 30 seconds) |
| `error` | Server → Client | Error notification |

---

## 7. Configuration

### 7.1 Server Configuration

```python
# server/app/config.py
class Settings:
    HOST: str = "0.0.0.0"
    PORT: int = 8765
    TLS_CERT: str | None = None          # Path to TLS certificate
    TLS_KEY: str | None = None           # Path to TLS private key
    MAX_CONNECTIONS: int = 50
    MAX_MESSAGE_SIZE: int = 131072       # 128KB for JSON messages
    MAX_CHUNK_SIZE: int = 65568          # 64KB + 32-byte header
    MAX_FILE_SIZE: int = 104857600       # 100MB
    PAIR_CODE_EXPIRY: int = 60           # seconds
    PAIR_MAX_ATTEMPTS: int = 5           # per minute per IP
    HEARTBEAT_INTERVAL: int = 30         # seconds
    HEARTBEAT_TIMEOUT: int = 90          # seconds before disconnect
```

### 7.2 Extension Configuration

Stored in `chrome.storage.local`:

```typescript
interface ExtensionConfig {
  serverUrl: string;          // e.g., "wss://192.168.1.100:8765"
  deviceId: string;           // UUID, generated on first run
  deviceName: string;         // User-friendly name, defaults to hostname
  autoConnect: boolean;       // Connect on browser start
  notifications: boolean;     // Show Chrome notifications
  theme: "light" | "dark" | "system";
  maxFileSize: number;        // bytes, default 100MB
}
```

---

## 8. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Latency (text) | < 100ms on LAN |
| Throughput (file) | Limited by network, not software |
| Max file size | 100MB (configurable) |
| Max paired devices | 10 per device |
| Reconnect time | < 5 seconds on LAN |
| Memory (server) | < 50MB for 50 connected devices |
| Memory (extension) | < 30MB during file transfer |
| Browser support | Chrome 120+, Edge 120+ (Chromium MV3) |

---

## 9. Future Considerations (Post-MVP)

These are explicitly **out of scope** for the phased plan above but documented for future reference:

- **Mobile companion app** — React Native or Flutter
- **WebRTC P2P mode** — direct device-to-device for LAN (skip relay)
- **Folder sync** — watch a folder, auto-sync changes
- **Persistent history** — encrypted local database of transfers
- **Multi-user support** — shared relay server for a team
- **Browser-to-browser tab sharing** — send current tab URL
- **Screen capture sharing** — screenshot + send
- **Cloud relay option** — hosted relay for cross-network use (would add cost)
