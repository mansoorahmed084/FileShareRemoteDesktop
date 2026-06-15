#!/usr/bin/env python3
"""
Native messaging host for the RemoteDesktop Chrome extension.
Starts/stops the relay server as a detached process so it survives
the native host exiting when the service worker goes to sleep.
"""

import json
import os
import signal
import struct
import subprocess
import sys
import time
import urllib.request

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(SERVER_DIR, ".server.pid")


def read_message():
    raw = sys.stdin.buffer.read(4)
    if not raw or len(raw) < 4:
        return None
    length = struct.unpack("=I", raw)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data.decode("utf-8"))


def send_message(msg):
    encoded = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def get_server_pid():
    if os.path.exists(PID_FILE):
        try:
            pid = int(open(PID_FILE).read().strip())
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True,
                )
                if str(pid) in result.stdout:
                    return pid
            else:
                os.kill(pid, 0)
                return pid
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
    return None


def is_server_running(port=8765):
    try:
        resp = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2)
        return resp.status == 200
    except Exception:
        return False


def find_python():
    for candidate in [
        os.path.join(SERVER_DIR, ".venv", "Scripts", "python.exe"),
        os.path.join(SERVER_DIR, ".venv", "bin", "python"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def start_server(port=8765, host="0.0.0.0"):
    pid = get_server_pid()
    if pid and is_server_running(port):
        return {"type": "server_status", "running": True, "pid": pid, "port": port}

    python = find_python()
    cmd = [python, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)]

    if sys.platform == "win32":
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        proc = subprocess.Popen(
            cmd, cwd=SERVER_DIR,
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            cmd, cwd=SERVER_DIR,
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        )

    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))

    for _ in range(20):
        time.sleep(0.5)
        if is_server_running(port):
            return {"type": "server_status", "running": True, "pid": proc.pid, "port": port}

    return {"type": "server_status", "running": False, "error": "Server failed to start within 10s"}


def stop_server():
    pid = get_server_pid()
    if pid:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
    return {"type": "server_status", "running": False}


def main():
    while True:
        msg = read_message()
        if msg is None:
            break

        cmd = msg.get("type", "")
        port = msg.get("port", 8765)

        if cmd == "start_server":
            send_message(start_server(port=port))
        elif cmd == "stop_server":
            send_message(stop_server())
        elif cmd == "server_status":
            pid = get_server_pid()
            running = is_server_running(port)
            send_message({"type": "server_status", "running": running, "pid": pid, "port": port})
        elif cmd == "ping":
            send_message({"type": "pong"})
        else:
            send_message({"type": "error", "message": f"Unknown command: {cmd}"})


if __name__ == "__main__":
    main()
