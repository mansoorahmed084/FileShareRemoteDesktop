# RemoteDesktop — Secure Device Bridge

Share files and text between your devices securely through a Chrome extension and self-hosted relay server.

## Quick Start

### 1. Start the Relay Server

```bash
cd server
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
```

Or with Docker:

```bash
docker compose up -d
```

### 2. Load the Chrome Extension

```bash
cd extension
npm install
npm run build
```

1. Open `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `extension/dist` folder

### 3. Connect and Pair

1. Click the RemoteDesktop extension icon
2. Enter server URL (default: `ws://localhost:8765`)
3. Click **Connect**
4. On Device A: click **Show Pairing Code**
5. On Device B: enter the 6-digit code
6. Verify the emoji sequence matches on both devices

## Features

- **Text sharing** — send text, code snippets, and .env variables
- **File transfer** — drag-and-drop files up to 100MB with progress tracking
- **E2E encryption** — ECDH P-256 key exchange + AES-256-GCM
- **Zero-knowledge server** — relay only, never sees plaintext
- **Side panel dashboard** — full UI with device management

## Security

| Layer | Mechanism |
|-------|-----------|
| Transport | WSS (TLS WebSocket) |
| Key Exchange | ECDH P-256 |
| Encryption | AES-256-GCM |
| Key Derivation | HKDF-SHA256 |
| Integrity | SHA-256 file hash verification |
| Pairing | 6-digit code + emoji verification |

### TLS Setup (Production)

```bash
cd server
python generate_cert.py --hostname your-hostname
RD_TLS_CERT=cert.pem RD_TLS_KEY=key.pem python -m uvicorn app.main:app --host 0.0.0.0 --port 8765
```

## Development

### Server

```bash
cd server
pip install -r requirements.txt
pip install pytest pytest-asyncio
pytest tests/
```

### Extension

```bash
cd extension
npm install
npm run dev      # Watch mode
npm run build    # Production build
```

## Architecture

```
Chrome Extension ←→ WSS ←→ FastAPI Relay ←→ WSS ←→ Chrome Extension
     (React)                 (Python)                  (React)
     AES-GCM                 Opaque relay              AES-GCM
```

See [docs/design.md](docs/design.md) for the full architecture document.
