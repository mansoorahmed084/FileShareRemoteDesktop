#!/usr/bin/env python3
"""
RemoteDesktop — Setup & Run Script

Usage:
  python setup.py              # Install deps + run server
  python setup.py --setup      # Install deps only
  python setup.py --run        # Run server only (skip install)
  python setup.py --tls        # Generate TLS cert, install deps, run with TLS
  python setup.py --test       # Install deps + run tests
  python setup.py --docker       # Build and run via Docker Compose
  python setup.py --extension    # Build the Chrome extension
  python setup.py --screen-deps  # Install screen sharing dependencies (uses Python 3.12 venv)
  python setup.py --native-host <extension-id>  # Register native messaging host
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

if platform.system() == "Windows":
    import winreg

ROOT = Path(__file__).resolve().parent
SERVER_DIR = ROOT / "server"
EXTENSION_DIR = ROOT / "extension"
VENV_DIR = SERVER_DIR / ".venv"
REQUIREMENTS = SERVER_DIR / "requirements.txt"

IS_WIN = platform.system() == "Windows"
PYTHON_BIN = VENV_DIR / ("Scripts" if IS_WIN else "bin") / ("python.exe" if IS_WIN else "python")
PIP_BIN = VENV_DIR / ("Scripts" if IS_WIN else "bin") / ("pip.exe" if IS_WIN else "pip")

# pydantic-core requires pre-built wheels; Python 3.14+ is too new.
# Prefer Python 3.12 or 3.13 when creating the venv on Windows.
_PREFERRED_VERSIONS = ["3.12", "3.13"]


def _find_python_for_venv() -> str:
    """Return path to a Python interpreter compatible with all dependencies."""
    if IS_WIN:
        py = shutil.which("py")
        if py:
            for ver in _PREFERRED_VERSIONS:
                try:
                    r = subprocess.run(
                        [py, f"-{ver}", "-c", "import sys; print(sys.executable)"],
                        capture_output=True, text=True,
                    )
                    if r.returncode == 0:
                        return r.stdout.strip()
                except FileNotFoundError:
                    pass
    # Fall back to whatever python is on PATH
    return sys.executable


def log(msg: str) -> None:
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, cwd=cwd, env=merged_env)
    return result.returncode


def check_python_version() -> None:
    if sys.version_info < (3, 11):
        print(f"Python 3.11+ required. You have {sys.version}")
        sys.exit(1)


def create_venv() -> None:
    if VENV_DIR.exists():
        print(f"  Virtual environment exists: {VENV_DIR}")
        return
    log("Creating virtual environment")
    python = _find_python_for_venv()
    print(f"  Using interpreter: {python}")
    rc = subprocess.run([python, "-m", "venv", str(VENV_DIR)]).returncode
    if rc != 0:
        print("  Failed to create virtual environment")
        sys.exit(1)
    print(f"  Created: {VENV_DIR}")


def install_server_deps(include_test: bool = False) -> None:
    log("Installing server dependencies")
    rc = run([str(PIP_BIN), "install", "-r", str(REQUIREMENTS), "--quiet"])
    if rc != 0:
        print("  Failed to install dependencies")
        sys.exit(1)
    if include_test:
        run([str(PIP_BIN), "install", "pytest", "pytest-asyncio", "--quiet"])
    print("  Done")


def install_screen_deps() -> None:
    log("Installing screen sharing dependencies")
    screen_req = ROOT / "screen" / "requirements.txt"
    if not screen_req.exists():
        print(f"  Not found: {screen_req}")
        sys.exit(1)
    rc = run([str(PIP_BIN), "install", "-r", str(screen_req)])
    if rc != 0:
        print("  Failed to install screen dependencies")
        sys.exit(1)
    print("  Done")
    print(f"\n  Run screen sharing with:")
    print(f"    {PYTHON_BIN} -m screen host -s ws://<ip>:8765")
    print(f"    {PYTHON_BIN} -m screen view -s ws://<ip>:8765 --code <code>")


def generate_tls_cert() -> None:
    log("Generating self-signed TLS certificate")
    cert_path = SERVER_DIR / "cert.pem"
    key_path = SERVER_DIR / "key.pem"
    if cert_path.exists() and key_path.exists():
        print(f"  Certificates already exist: {cert_path}")
        return
    rc = run(
        [str(PYTHON_BIN), str(SERVER_DIR / "generate_cert.py"),
         "--cert", str(cert_path), "--key", str(key_path)],
        cwd=SERVER_DIR,
    )
    if rc != 0:
        print("  Failed to generate certificates")
        sys.exit(1)


def run_server(tls: bool = False, host: str = "0.0.0.0", port: int = 8765) -> None:
    log(f"Starting relay server on {host}:{port}" + (" (TLS)" if tls else ""))
    print(f"  Server URL: {'wss' if tls else 'ws'}://localhost:{port}")
    print(f"  Health:     http{'s' if tls else ''}://localhost:{port}/health")
    print(f"  Press Ctrl+C to stop\n")

    env = {}
    if tls:
        env["RD_TLS_CERT"] = str(SERVER_DIR / "cert.pem")
        env["RD_TLS_KEY"] = str(SERVER_DIR / "key.pem")

    cmd = [
        str(PYTHON_BIN), "-m", "uvicorn", "app.main:app",
        "--host", host,
        "--port", str(port),
        "--reload",
    ]
    if tls:
        cmd += ["--ssl-certfile", str(SERVER_DIR / "cert.pem")]
        cmd += ["--ssl-keyfile", str(SERVER_DIR / "key.pem")]

    try:
        run(cmd, cwd=SERVER_DIR, env=env)
    except KeyboardInterrupt:
        print("\n  Server stopped.")


def run_tests() -> None:
    log("Running server tests")
    rc = run(
        [str(PYTHON_BIN), "-m", "pytest", "tests/", "-v"],
        cwd=SERVER_DIR,
    )
    sys.exit(rc)


def build_extension() -> None:
    log("Building Chrome extension")
    npm = shutil.which("npm")
    if not npm:
        print("  npm not found. Install Node.js first.")
        sys.exit(1)

    if not (EXTENSION_DIR / "node_modules").exists():
        print("  Installing npm dependencies...")
        rc = run([npm, "install"], cwd=EXTENSION_DIR)
        if rc != 0:
            print("  npm install failed")
            sys.exit(1)

    print("  Building...")
    rc = run([npm, "run", "build"], cwd=EXTENSION_DIR)
    if rc != 0:
        print("  Build failed")
        sys.exit(1)

    print(f"\n  Extension built: {EXTENSION_DIR / 'dist'}")
    print("  Load it in Chrome:")
    print("    1. Open chrome://extensions/")
    print("    2. Enable 'Developer mode'")
    print("    3. Click 'Load unpacked'")
    print(f"    4. Select: {EXTENSION_DIR / 'dist'}")


NATIVE_HOST_NAME = "com.remotedesktop.relay"


def register_native_host(extension_id: str) -> None:
    log("Registering native messaging host")

    bat_path = SERVER_DIR / "start_host.bat"
    manifest_path = SERVER_DIR / f"{NATIVE_HOST_NAME}.json"

    manifest = {
        "name": NATIVE_HOST_NAME,
        "description": "RemoteDesktop Relay Server Host",
        "path": str(bat_path),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"  Manifest written: {manifest_path}")

    if IS_WIN:
        key_path = f"Software\\Google\\Chrome\\NativeMessagingHosts\\{NATIVE_HOST_NAME}"
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))
            winreg.CloseKey(key)
            print(f"  Registry key set: HKCU\\{key_path}")
        except Exception as e:
            print(f"  Failed to set registry key: {e}")
            sys.exit(1)
    else:
        if sys.platform == "darwin":
            target = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "NativeMessagingHosts"
        else:
            target = Path.home() / ".config" / "google-chrome" / "NativeMessagingHosts"
        target.mkdir(parents=True, exist_ok=True)
        dest = target / f"{NATIVE_HOST_NAME}.json"
        shutil.copy2(manifest_path, dest)
        print(f"  Manifest copied to: {dest}")

    print(f"\n  Native host registered for extension: {extension_id}")
    print("  Restart Chrome for the change to take effect.")
    print("  The extension can now start/stop the server with one click.")


def run_docker() -> None:
    log("Starting with Docker Compose")
    docker = shutil.which("docker")
    if not docker:
        print("  Docker not found. Install Docker first.")
        sys.exit(1)
    try:
        run([docker, "compose", "up", "--build", "-d"], cwd=ROOT)
        print("\n  Server running at ws://localhost:8765")
        print("  Stop with: docker compose down")
    except KeyboardInterrupt:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RemoteDesktop — Setup & Run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--setup", action="store_true", help="Install dependencies only")
    parser.add_argument("--run", action="store_true", help="Run server only (skip install)")
    parser.add_argument("--tls", action="store_true", help="Generate TLS cert and run with TLS")
    parser.add_argument("--test", action="store_true", help="Run server tests")
    parser.add_argument("--docker", action="store_true", help="Run via Docker Compose")
    parser.add_argument("--extension", action="store_true", help="Build Chrome extension")
    parser.add_argument("--native-host", metavar="EXTENSION_ID",
                        help="Register native messaging host (get ID from chrome://extensions)")
    parser.add_argument("--screen-deps", action="store_true", help="Install screen sharing dependencies")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Server port (default: 8765)")

    args = parser.parse_args()

    check_python_version()

    if args.native_host:
        create_venv()
        install_server_deps()
        register_native_host(args.native_host)
        return

    if args.screen_deps:
        create_venv()
        install_screen_deps()
        return

    if args.docker:
        run_docker()
        return

    if args.extension:
        build_extension()
        return

    if args.run:
        run_server(tls=args.tls, host=args.host, port=args.port)
        return

    create_venv()

    if args.test:
        install_server_deps(include_test=True)
        run_tests()
        return

    install_server_deps()

    if args.setup:
        log("Setup complete")
        print(f"  Run the server:  python setup.py --run")
        print(f"  Build extension: python setup.py --extension")
        return

    if args.tls:
        generate_tls_cert()

    run_server(tls=args.tls, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
