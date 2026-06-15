# RemoteDesktop with secure File Sharing

**Secure, encrypted device bridge for developers.** Share files, text, `.env` variables, and code snippets between your laptops instantly — no cloud, no accounts, no cost.

```
Laptop A (Chrome/CLI/Agent) ◄──── WSS (E2E encrypted) ────► Relay Server ◄──── WSS ────► Laptop B (Chrome/CLI/Agent)
```

RemoteDesktop is a **Chrome extension** + **CLI tool** + **MCP server** paired with a **self-hosted Python relay server**. All data is end-to-end encrypted — the server is zero-knowledge and never sees your plaintext.

> **⚠️ Development Use Only**
>
> This tool is built for **developer workflows on trusted networks** (home lab, office LAN, personal VPS). It is **not** intended for production, enterprise, or public-facing deployment. While the encryption stack is robust, the project has not undergone a formal security audit. Use at your own risk — the authors assume no liability for data loss, exposure, or misuse. **Do not use this as your sole mechanism for transferring highly sensitive credentials in regulated environments.**

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
| **CLI tool** | Terminal-based sharing: `rdcli send`, `rdcli send-file`, `rdcli send-env`, `rdcli listen` |
| **MCP server** | AI agent integration — Claude, Cursor, and other coding agents can send/receive files and text |

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

## One-Click Server (Native Messaging Host)

Instead of running the server from a terminal every time, you can register a **native messaging host** that lets the Chrome extension start/stop the relay server with a single click.

### Setup (one time)

1. Build and load the extension first (see [Quick Start](#quick-start) steps 2–3)
2. Copy your extension ID from `chrome://extensions/` (e.g., `abcdefghijklmnopqrstuvwxyz123456`)
3. Register the native host:

```bash
python setup.py --native-host <your-extension-id>
```

4. Restart Chrome

### Usage

- Open the extension popup — the **Local Server** panel shows the server status
- Click **Start Server & Connect** — starts the server and connects automatically
- When connected, the Settings tab shows a **Stop** button to shut down the server
- The server runs as a detached process — it survives even if the popup closes

> **Note:** The native host requires Python and the server dependencies to be installed. `setup.py --native-host` handles the venv and deps automatically.

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
python setup.py --native-host <id>  # Register native messaging host for one-click server
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

2. Open port 8765 in the firewall on **both** machines (see [Firewall rules](#firewall-rules) below)
3. Start the server on **one** machine only: `python setup.py`
4. On both laptops, connect the extension to `ws://192.168.1.42:8765` (replace with the server machine's IP)

### Different networks (home ↔ office)

1. Deploy the relay server to a cloud VPS ($5/mo on any provider)
2. Use TLS: `python setup.py --tls`
3. Point both extensions to `wss://<your-vps-ip>:8765`

### Firewall rules

**Important:** You must open port 8765 on **both** machines — the machine running the server **and** any machine connecting to it. Without this, WebSocket connections will be silently blocked.

**Windows (run PowerShell as Administrator on both machines):**
```powershell
New-NetFirewallRule -DisplayName "RemoteDesktop Relay" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
```

**macOS (on both machines):**
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/local/bin/python3
```

**Linux (on both machines):**
```bash
sudo ufw allow 8765/tcp
```

> **Tip:** If `ping` between machines fails but the server's `/health` endpoint responds in a browser, that's normal — Windows Firewall blocks ICMP (ping) by default. As long as the TCP port is open, the extension will connect fine.

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
| CLI | Python, Click, Rich |
| MCP Server | MCP SDK (Model Context Protocol), stdio transport |
| Containerization | Docker, multi-stage build |

### Project structure

```
FileShareRemoteDesktop/
├── server/                     # Python relay server
│   ├── app/
│   │   ├── main.py             # FastAPI app, WebSocket endpoint
│   │   ├── hub.py              # Connection manager
│   │   ├── registry.py         # Device pairing logic
│   │   ├── middleware.py        # Rate limiting, size limits
│   │   ├── models.py           # Pydantic message schemas
│   │   └── config.py           # Settings (env-configurable)
│   ├── tests/                  # pytest test suite
│   ├── native_host.py          # Native messaging host (start/stop server from Chrome)
│   ├── start_host.bat          # Windows batch wrapper for native host
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
├── cli/                        # CLI & MCP Server
│   ├── client.py               # Shared WebSocket client library
│   ├── rdcli.py                # Click-based CLI tool
│   ├── mcp_server.py           # MCP server for AI agents
│   └── requirements.txt
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

## CLI Tool

A terminal-based client for sharing text, files, and `.env` variables without Chrome.

### Install

```bash
cd cli
pip install -r requirements.txt
```

### Commands

```bash
# Connect and listen for incoming messages/files
python rdcli.py connect --server ws://192.168.1.42:8765 --name "My Laptop"

# Check config
python rdcli.py status

# Pair devices
python rdcli.py pair create --server ws://192.168.1.42:8765
python rdcli.py pair join 482910 --server ws://192.168.1.42:8765

# Send text
python rdcli.py send <device-id-or-name> "Hello from terminal"

# Send a file
python rdcli.py send-file <device-id-or-name> ./report.pdf

# Send .env variables
python rdcli.py send-env <device-id-or-name> ./.env

# List paired devices
python rdcli.py devices --server ws://192.168.1.42:8765

# Listen and auto-save received files
python rdcli.py listen --server ws://192.168.1.42:8765 --save-dir ./downloads
```

The CLI stores config at `~/.remote-desktop/config.json` — once connected, server URL and device name are remembered.

---

## MCP Server (AI Agent Integration)

The MCP server lets AI coding agents (Claude Code, Claude Desktop, Cursor, etc.) send and receive files/text between paired devices.

### Available Tools

| Tool | Description |
|------|-------------|
| `rd_list_devices` | List paired devices and their online/offline status |
| `rd_send_text` | Send text, code snippets, or config to a device |
| `rd_send_file` | Send a file (up to 100MB) to a device |
| `rd_send_env_file` | Read and send a `.env` file to a device |
| `rd_get_messages` | Get recent received text messages |
| `rd_get_received_files` | List files received from other devices |
| `rd_save_received_file` | Save a received file to disk |
| `rd_pair_create` | Generate a 6-digit pairing code |
| `rd_pair_join` | Join using a pairing code |
| `rd_get_status` | Get connection status and device info |

### Configure in Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "remote-desktop": {
      "command": "python",
      "args": ["/absolute/path/to/cli/mcp_server.py", "--server", "ws://192.168.1.42:8765"]
    }
  }
}
```

### Configure in Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "remote-desktop": {
      "command": "python",
      "args": ["/absolute/path/to/cli/mcp_server.py", "--server", "ws://192.168.1.42:8765"]
    }
  }
}
```

### Example Usage with Claude

Once configured, you can ask Claude:

> "Send my .env file to my work laptop"
> "List my connected devices"
> "Send this API key to Device B: sk-abc123..."
> "Check if I received any files"

The MCP server auto-connects to the relay on first tool call and reuses the connection for subsequent calls.

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

- [x] CLI tool for terminal-based sharing
- [x] MCP server for AI agent integration
- [x] One-click server start/stop from Chrome extension (native messaging host)
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

## Security Disclaimer

This software is provided **as-is** for development and personal use. It has **not** been independently audited by a third-party security firm.

- **No warranty.** The authors make no guarantees about the security, reliability, or fitness of this tool for any particular purpose.
- **Not for production.** Do not deploy this in environments subject to compliance requirements (HIPAA, SOC 2, PCI-DSS, etc.) without a professional security review.
- **Self-signed TLS.** The built-in certificate generator creates self-signed certs suitable for LAN use. For internet-facing deployments, use certificates from a trusted CA (e.g., Let's Encrypt).
- **Relay trust.** While the relay server is zero-knowledge by design, whoever operates the server can observe connection metadata (device IDs, message sizes, timestamps). Self-host the relay if metadata privacy matters to you.
- **Report vulnerabilities.** If you discover a security issue, please open a GitHub issue or contact the maintainer directly.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
