# RemoteDesktop — Usage Guide

## Overview

RemoteDesktop lets you share text and files between two (or more) laptops through a Chrome extension connected to a self-hosted relay server. One laptop runs the relay server; all laptops run the Chrome extension.

```
┌─────────────┐        ┌─────────────────┐        ┌─────────────┐
│  Laptop A   │  WSS   │  Relay Server   │  WSS   │  Laptop B   │
│  (Chrome)   │◄──────►│  (runs on A or  │◄──────►│  (Chrome)   │
│             │        │   separate box) │        │             │
└─────────────┘        └─────────────────┘        └─────────────┘
```

---

## Step 1: Choose Where to Run the Server

The relay server needs to be reachable by all devices. You have three options:

| Option | When to use | URL format |
|--------|-------------|------------|
| **Same laptop** | Both laptops on same Wi-Fi | `ws://<your-local-ip>:8765` |
| **Separate machine** | Dedicated server on LAN | `ws://<server-ip>:8765` |
| **Cloud VPS** | Laptops on different networks | `wss://<your-domain>:8765` |

### Find your local IP

**Windows:**
```powershell
ipconfig | Select-String "IPv4"
# Example output: IPv4 Address. . . . . . . . . . . : 192.168.1.42
```

**macOS / Linux:**
```bash
hostname -I | awk '{print $1}'
# or
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Your server URL will be: `ws://192.168.1.42:8765` (replace with your actual IP).

---

## Step 2: Start the Relay Server (on one machine)

You have two options: start from the **extension with one click** (recommended), or from the **terminal**.

### Option A: One-click start from Chrome (recommended)

If you've set up the native messaging host (see [Native Host Setup](#native-host-setup) below), you can start the server directly from the extension popup:

1. Click the RemoteDesktop icon in Chrome
2. Click **Start Server & Connect**
3. The server starts in the background and the extension connects automatically

The server runs as a background process — it keeps running even if you close the popup. You can stop it from the extension's **Settings** tab.

### Option B: Terminal start

```bash
cd myRemoteDesktop
python setup.py
```

This creates a virtual environment, installs dependencies, and starts the server on `0.0.0.0:8765`.

### With TLS (recommended for non-LAN use)

```bash
python setup.py --tls
```

This generates a self-signed certificate and starts the server with WSS. Your URL becomes `wss://192.168.1.42:8765`.

### With Docker

```bash
python setup.py --docker
```

### Custom port

```bash
python setup.py --port 9000
```

### Verify the server is running

From any machine on the network, open a browser and visit:

```
http://192.168.1.42:8765/health
```

You should see:

```json
{"status": "ok", "connected_devices": 0, "timestamp": 1718400000}
```

---

## Step 3: Build and Install the Chrome Extension (on each laptop)

### Build

```bash
cd myRemoteDesktop/extension
npm install
npm run build
```

Or from the root:

```bash
python setup.py --extension
```

### Load into Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Toggle **Developer mode** ON (top-right)
3. Click **Load unpacked**
4. Select the `extension/dist` folder
5. The RemoteDesktop icon appears in your toolbar

> **Tip:** You need to do this on **every laptop** you want to connect. Copy the entire `myRemoteDesktop` folder to the other laptop, or just copy the `extension/dist` folder.

---

## Step 4: Connect to the Server (on each laptop)

1. Click the **RemoteDesktop** extension icon in Chrome
2. Enter the server URL:
   - Same network: `ws://192.168.1.42:8765`
   - With TLS: `wss://192.168.1.42:8765`
3. Give your device a name (e.g., "Work Laptop", "Home Desktop")
4. Click **Connect**
5. The status badge should turn green: **Connected**

Do this on both laptops.

---

## Step 5: Pair the Two Laptops

Pairing is a one-time setup per device pair.

### On Laptop A:

1. Go to the **Devices** tab
2. Click **Show Pairing Code**
3. A 6-digit code appears (e.g., `847293`)
4. The code expires in 60 seconds

### On Laptop B:

1. Go to the **Devices** tab
2. Click **Enter a Code**
3. Type the 6-digit code from Laptop A
4. Click **Connect**

### Verify the pairing:

Both laptops will show a **4-emoji sequence** (e.g., 🔒🌟🎯💎). Confirm the emojis match on both screens, then click **They Match**.

The devices are now paired and end-to-end encrypted.

---

## Step 6: Share Text

1. Click on the paired device in the **Devices** tab (or go to the **Text** tab)
2. Type or paste text in the textarea
3. Press **Ctrl+Enter** or click **Send**
4. The text appears on the other laptop instantly

### Sharing .env variables

Paste your `.env` content directly — the extension detects env variable format and displays it with monospace formatting:

```
DATABASE_URL=postgres://user:pass@localhost:5432/mydb
API_KEY=sk-abc123
SECRET=my-secret-value
```

The receiver can click **Copy** to copy the entire block to their clipboard.

---

## Step 7: Share Files

1. Go to the **Files** tab
2. Make sure a paired device is selected (select one in the Devices tab first)
3. **Drag and drop** files onto the drop zone, or click to browse
4. The file transfers with a progress bar showing speed and percentage
5. On the receiving laptop, click **Save** to download the file

**Limits:**
- Max file size: 100MB per file
- Multiple files can be sent at once
- Files are encrypted in 64KB chunks during transfer

---

## Network Setup & Firewall

### Windows Firewall

If laptops can't connect, allow port 8765 through the firewall on the server machine:

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "RemoteDesktop Relay" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
```

### macOS Firewall

```bash
# Temporarily allow (or add via System Preferences > Security > Firewall)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/local/bin/python3
```

### Linux (ufw)

```bash
sudo ufw allow 8765/tcp
```

### Router / Different Networks

If your laptops are on **different Wi-Fi networks** (e.g., home and office):

1. Run the relay server on a cloud VPS (any cheap $5/mo VPS works)
2. Use TLS: `python setup.py --tls`
3. Point both extensions to `wss://<vps-ip>:8765`
4. Or use a reverse proxy (nginx/caddy) with a real domain and Let's Encrypt cert

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Extension shows "Offline" | Check server URL — is the server running? Can you reach `http://<ip>:8765/health`? |
| Can't connect from other laptop | Check firewall rules. Make sure both laptops are on the same network. |
| Pairing code rejected | Code expires in 60 seconds. Generate a new one. |
| Emoji verification doesn't match | Something intercepted the key exchange. Disconnect, unpair, and re-pair. |
| File transfer stuck | Check if the receiving device is still online. Cancel and retry. |
| "WebSocket connection failed" | If using `wss://` with self-signed cert, visit `https://<ip>:8765/health` in Chrome first and accept the certificate warning. |
| Extension not loading | Make sure you loaded the `dist` folder (not `src`). Check `chrome://extensions/` for errors. |

### Accept self-signed certificates

When using `--tls` with a self-signed cert, Chrome will block the WebSocket connection by default. Fix:

1. Open `https://192.168.1.42:8765/health` in Chrome
2. Click **Advanced** → **Proceed to 192.168.1.42 (unsafe)**
3. You should see the health JSON response
4. Now the extension can connect via `wss://`

---

## Native Host Setup

The native messaging host lets the Chrome extension start/stop the relay server with one click — no terminal needed. This is a **one-time setup** per machine.

### 1. Build and load the extension first

Follow Steps 3 and Load into Chrome above.

### 2. Copy your extension ID

1. Go to `chrome://extensions/`
2. Find **RemoteDesktop**
3. Copy the ID string (e.g., `galfkgdlepjdddkoojckplfmdgjiffoh`)

### 3. Register the native host

```bash
python setup.py --native-host <your-extension-id>
```

This:
- Creates the native host manifest (`server/com.remotedesktop.relay.json`)
- Registers it in the Windows registry (or copies to the appropriate Chrome config directory on macOS/Linux)
- Ensures the Python venv and server dependencies are installed

### 4. Restart Chrome

Close **all** Chrome windows and reopen Chrome. The native host won't be recognized until Chrome restarts.

### 5. Test it

Click the RemoteDesktop icon — you should see a **Local Server** panel with a **Start Server & Connect** button. Click it, and the server should start and the extension should connect automatically.

### Troubleshooting native host

| Problem | Solution |
|---------|----------|
| "Native host not registered" error | Re-run `python setup.py --native-host <id>` and restart Chrome |
| Server starts but extension doesn't connect | Wait a few seconds — the host polls `/health` for up to 10s |
| Button says "Starting..." forever | Check that Python and uvicorn are installed in the server venv |
| Extension ID changed after reload | Re-run `python setup.py --native-host <new-id>` — the ID changes when you remove and re-add the extension |

---

## Quick Reference

```bash
# Server machine (terminal)
python setup.py                    # Install + run server
python setup.py --tls              # Install + run with TLS
python setup.py --run              # Run only (already installed)
python setup.py --run --port 9000  # Custom port
python setup.py --test             # Run tests
python setup.py --docker           # Docker mode

# Each client machine
python setup.py --extension        # Build Chrome extension
# Then load extension/dist in chrome://extensions/

# One-click server setup (one time per machine)
python setup.py --native-host <extension-id>  # Register native host
# Then restart Chrome — "Start Server & Connect" button appears in popup
```

### Connection checklist

- [ ] Extension loaded in Chrome on both laptops
- [ ] Native host registered (or server started from terminal)
- [ ] Server running and reachable (`/health` returns OK)
- [ ] Firewall allows port 8765 on **both** machines
- [ ] Both extensions connected (green status badge)
- [ ] Devices paired (6-digit code + emoji verification)
- [ ] Ready to share!
