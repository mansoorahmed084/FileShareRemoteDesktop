# RemoteDesktop

**Secure, encrypted device bridge for developers.** Share files, text, `.env` variables, and code snippets between your laptops instantly — no cloud, no accounts, no cost.

```
Laptop A (Chrome) ◄──── WSS (E2E encrypted) ────► Relay Server ◄──── WSS ────► Laptop B (Chrome)
```

RemoteDesktop is a **Chrome extension** paired with a **self-hosted Python relay server**. All data is end-to-end encrypted — the server is zero-knowledge and never sees your plaintext.

---

## Why?

- You work on multiple machines and need to move `.env` files, API keys, or config snippets
- You don't want to email/Slack sensitive credentials to yourself
- You're tired of USB drives and cloud upload/download cycles
- You want something free, open-source, and under your control

---

## Features

| Feature | Details |
|---------|---------|
| **Text sharing** | Send any text, code snippets, or multi-line content instantly |
| **Env variable sharing** | Paste `.env` content — auto-detected with monospace formatting and one-click copy |
| **File transfer** | Drag-and-drop files up to 100MB with real-time progress, speed, and ETA |
| **End-to-end encryption** | ECDH P-256 key exchange + AES-256-GCM — server never sees plaintext |
| **Device pairing** | 6-digit code + 4-emoji visual verification |
| **Side panel dashboard** | Full UI with tabs for Devices, Text, Files, and Settings |
| **Auto-reconnect** | Exponential backoff (1s → 30s) with automatic session recovery |
| **Self-hosted** | Run on your LAN for free, or deploy to a VPS for cross-network use |
| **Docker support** | One-command deployment with `docker compose up` |
| **Zero accounts** | No sign-up, no login, no tracking — just device IDs and pairing codes |

---

## Quick Start

### Prerequisites

- **Python 3.11+** (for the relay server)
- **Node.js 18+** and **npm** (for building the Chrome extension)
- **Chrome** or any Chromium browser (Edge, Brave, Arc, etc.)

### 1. Clone and set up

```bash
git clone https://github.com/mansoorahmed084/FileShareRemoteDesktop.git
cd FileShareRemoteDesktop
python setup.py
```

This creates a virtual environment, installs all Python dependencies, and starts the relay server on port `8765`.

### 2. Build the Chrome extension

Open a new terminal:

```bash
python setup.py --extension
```

### 3. Load the extension in Chrome

1. Open `chrome://extensions/`
2. Toggle **Developer mode** ON (top-right corner)
3. Click **Load unpacked**
4. Select the `extension/dist` folder

### 4. Connect

1. Click the RemoteDesktop icon in Chrome's toolbar
2. Enter the server URL: `ws://localhost:8765`
3. Give your device a name (e.g., "Work Laptop")
4. Click **Connect** — status badge turns green

### 5. Pair a second device

Repeat steps 1–4 on your other laptop (use `ws://<server-ip>:8765`), then:

- **Laptop A:** Devices tab → **Show Pairing Code** → note the 6-digit code
- **Laptop B:** Devices tab → **Enter a Code** → type the code → **Connect**
- **Both:** Verify the 4-emoji sequence matches → click **They Match**

You're paired. Start sharing!

---

## Setup Script Reference

The `setup.py` script handles everything:

```bash
python setup.py                     # Install deps + start server
python setup.py --setup             # Install deps only
python setup.py --run               # Start server (skip install)
python setup.py --run --port 9000   # Custom port
python setup.py --tls               # Generate self-signed cert + start with TLS
python setup.py --test              # Install deps + run test suite
python setup.py --extension         # Build the Chrome extension
python setup.py --docker            # Build and run via Docker Compose
```

---

## Connecting Two Laptops

### Same Wi-Fi network

1. Find the server machine's local IP:

   **Windows:**
   ```powershell
   ipconfig | Select-String "IPv4"
   ```

   **macOS / Linux:**
   ```bash
   hostname -I | awk '{print $1}'
   ```

2. Start the server on that machine: `python setup.py`
3. On both laptops, connect the extension to `ws://192.168.1.42:8765` (replace with your IP)

### Different networks (home ↔ office)

1. Deploy the relay server to a cloud VPS ($5/mo on any provider)
2. Use TLS: `python setup.py --tls`
3. Point both extensions to `wss://<your-vps-ip>:8765`

### Firewall rules

If devices can't connect, open port 8765:

**Windows (run as Administrator):**
```powershell
New-NetFirewallRule -DisplayName "RemoteDesktop Relay" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
```

**macOS:**
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/local/bin/python3
```

**Linux (ufw):**
```bash
sudo ufw allow 8765/tcp
```

---

## Security

### Encryption stack

| Layer | Algorithm | Purpose |
|-------|-----------|---------|
| Transport | TLS 1.3 (WSS) | Protects data in transit |
| Key Exchange | ECDH P-256 | Establishes shared secret between devices |
| Key Derivation | HKDF-SHA256 | Derives AES key from shared secret |
| Payload Encryption | AES-256-GCM | Encrypts all text and file chunks |
| File Integrity | SHA-256 | Verifies file wasn't corrupted or tampered with |
| Pairing Verification | Emoji fingerprint | Visual confirmation that no MITM occurred |

### Threat model

| Threat | How it's mitigated |
|--------|-------------------|
| Server compromise | E2E encryption — server only relays opaque encrypted blobs |
| Man-in-the-middle | TLS + ECDH key exchange with visual emoji verification |
| Replay attacks | Per-message random nonce + timestamp validation |
| Device impersonation | HMAC device tokens + pairing codes |
| Unauthorized access | 6-digit pairing code, expires in 60 seconds |
| Data at rest on server | Nothing stored — relay only, no persistence |
| Brute-force pairing | Rate limited to 5 attempts per minute per IP |

### What the server knows

The relay server knows:
- Which device IDs are connected
- Which devices are paired (to route messages)
- Message sizes and timestamps

The relay server **never** knows:
- Message content (encrypted with AES-256-GCM)
- File contents or filenames (encrypted)
- Encryption keys (derived client-side only)

---

## Architecture

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
│  │ Popup / Side  │  │         │  │ Device      │  │         │  │ Popup / Side  │  │
│  │ Panel (React) │  │         │  │ Registry    │  │         │  │ Panel (React) │  │
│  └───────────────┘  │         │  └─────────────┘  │         │  └───────────────┘  │
│                     │         │                   │         │                     │
│  Web Crypto API     │         │  No data stored.  │         │  Web Crypto API     │
│  (AES-256-GCM)      │         │  No decryption.   │         │  (AES-256-GCM)      │
│                     │         │  Relay only.      │         │                     │
└─────────────────────┘         └──────────────────┘         └─────────────────────┘
```

### Tech stack

| Component | Technology |
|-----------|-----------|
| Relay Server | Python 3.12, FastAPI, uvicorn, WebSockets |
| Chrome Extension | TypeScript, React 18, Vite, Tailwind CSS |
| Encryption (browser) | Web Crypto API (native, zero dependencies) |
| Encryption (server) | `cryptography` library (for TLS cert generation only) |
| Containerization | Docker, multi-stage build |

### Project structure

```
myRemoteDesktop/
├── server/                     # Python relay server
│   ├── app/
│   │   ├── main.py             # FastAPI app, WebSocket endpoint
│   │   ├── hub.py              # Connection manager
│   │   ├── registry.py         # Device pairing logic
│   │   ├── middleware.py        # Rate limiting, size limits
│   │   ├── models.py           # Pydantic message schemas
│   │   └── config.py           # Settings (env-configurable)
│   ├── tests/                  # pytest test suite
│   ├── generate_cert.py        # Self-signed TLS cert generator
│   ├── Dockerfile
│   └── requirements.txt
│
├── extension/                  # Chrome Extension (Manifest V3)
│   ├── src/
│   │   ├── background/         # Service worker (WebSocket, crypto, routing)
│   │   ├── popup/              # Quick-access popup UI
│   │   ├── sidepanel/          # Full dashboard UI
│   │   ├── components/         # React components
│   │   ├── hooks/              # Custom React hooks
│   │   └── lib/                # Crypto, WebSocket client, file transfer
│   ├── public/                 # Manifest, icons
│   └── dist/                   # Built extension (load this in Chrome)
│
├── docs/
│   ├── design.md               # Full architecture document
│   └── usage.md                # Detailed usage guide
│
├── setup.py                    # One-command setup and run script
├── docker-compose.yml
└── README.md
```

---

## Configuration

The server is configured via environment variables (prefixed with `RD_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `RD_HOST` | `0.0.0.0` | Server bind address |
| `RD_PORT` | `8765` | Server port |
| `RD_TLS_CERT` | — | Path to TLS certificate file |
| `RD_TLS_KEY` | — | Path to TLS private key file |
| `RD_MAX_CONNECTIONS` | `50` | Maximum simultaneous connections |
| `RD_MAX_MESSAGE_SIZE` | `131072` | Maximum JSON message size (bytes) |
| `RD_MAX_FILE_SIZE` | `104857600` | Maximum file size (100MB) |
| `RD_PAIR_CODE_EXPIRY` | `60` | Pairing code lifetime (seconds) |
| `RD_HEARTBEAT_INTERVAL` | `30` | Ping interval (seconds) |

---

## Docker Deployment

### Quick

```bash
docker compose up -d
```

### With TLS

```bash
# Generate certs first
cd server && python generate_cert.py && cd ..

# Mount certs and set env vars
docker compose -f docker-compose.yml up -d
```

### Custom docker-compose override

```yaml
services:
  relay:
    environment:
      - RD_PORT=9000
      - RD_MAX_CONNECTIONS=100
      - RD_TLS_CERT=/certs/cert.pem
      - RD_TLS_KEY=/certs/key.pem
    volumes:
      - ./server/cert.pem:/certs/cert.pem:ro
      - ./server/key.pem:/certs/key.pem:ro
    ports:
      - "9000:9000"
```

---

## Development

### Server

```bash
cd server
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Start dev server with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

### Extension

```bash
cd extension
npm install

npm run dev      # Watch mode — rebuilds on file changes
npm run build    # Production build → dist/
```

After rebuilding, go to `chrome://extensions/` and click the refresh icon on RemoteDesktop.

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server health check and connected device count |
| `GET` | `/devices` | List all connected devices |

### WebSocket Endpoint

`ws[s]://<host>:<port>/ws/<device_id>?name=<device_name>`

### Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `pair_create` | Client → Server | Request a 6-digit pairing code |
| `pair_code` | Server → Client | Return the generated code |
| `pair_join` | Client → Server | Redeem a pairing code |
| `pair_accept` | Server → Client | Pairing confirmed |
| `pair_reject` | Server → Client | Invalid or expired code |
| `key_exchange` | Client ↔ Client | ECDH public key exchange (via relay) |
| `text` | Client ↔ Client | Encrypted text message |
| `file_meta` | Client → Client | File metadata before transfer |
| `file_chunk` | Client → Client | Encrypted file chunk |
| `file_ack` | Client → Client | Chunk/file acknowledgment |
| `file_cancel` | Client → Client | Cancel ongoing transfer |
| `device_online` | Server → Client | Paired device connected |
| `device_offline` | Server → Client | Paired device disconnected |
| `ping` / `pong` | Both | Keepalive heartbeat |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Extension shows "Offline" | Is the server running? Check `http://<ip>:8765/health` in your browser |
| Can't connect from other laptop | Check firewall rules (see [Firewall rules](#firewall-rules) above) |
| Pairing code rejected | Codes expire in 60 seconds — generate a new one |
| Emoji verification doesn't match | Potential MITM — disconnect, unpair, and re-pair on a trusted network |
| File transfer stuck | Check if the other device is still online. Cancel and retry |
| WebSocket connection failed with `wss://` | For self-signed certs, visit `https://<ip>:8765/health` in Chrome first and accept the certificate warning |
| Extension won't load | Make sure you selected `extension/dist` (not `extension/src`). Check `chrome://extensions/` for error details |

---

## Roadmap

- [ ] Mobile companion app (React Native)
- [ ] WebRTC peer-to-peer mode for LAN (skip relay for faster transfers)
- [ ] Folder watching and auto-sync
- [ ] Browser tab URL sharing
- [ ] Screen capture and share
- [ ] Persistent encrypted transfer history

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run the test suite: `python setup.py --test`
5. Build the extension: `python setup.py --extension`
6. Submit a pull request

---

## License

MIT License. See [LICENSE](LICENSE) for details.
