"""CLI entry point — python -m screen host|view"""

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="screen",
        description="RemoteDesktop Screen Sharing & Remote Control",
    )
    sub = parser.add_subparsers(dest="command")

    host_p = sub.add_parser("host", help="Share your screen (others can view/control)")
    host_p.add_argument("--server", "-s", required=True, help="Relay server URL (ws://ip:8765)")
    host_p.add_argument("--name", "-n", default="Host", help="Device name")
    host_p.add_argument("--fps", type=int, default=30, help="Target FPS (default: 30)")
    host_p.add_argument("--monitor", "-m", type=int, default=0, help="Monitor index (default: 0)")
    host_p.add_argument("--input", action="store_true", help="Allow remote mouse/keyboard control")
    host_p.add_argument("--clipboard", action="store_true", help="Enable clipboard sync")

    view_p = sub.add_parser("view", help="View and control a remote screen")
    view_p.add_argument("--server", "-s", required=True, help="Relay server URL (ws://ip:8765)")
    view_p.add_argument("--name", "-n", default="Viewer", help="Device name")
    view_p.add_argument("--code", "-c", required=True, help="6-digit pairing code from host")
    view_p.add_argument("--input", action="store_true", help="Send mouse/keyboard to host")
    view_p.add_argument("--clipboard", action="store_true", help="Enable clipboard sync")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "host":
        from .host import run_host
        asyncio.run(run_host(
            server_url=args.server,
            device_name=args.name,
            fps=args.fps,
            monitor=args.monitor,
            enable_input=args.input,
            enable_clipboard=args.clipboard,
        ))
    elif args.command == "view":
        from .viewer import run_viewer
        asyncio.run(run_viewer(
            server_url=args.server,
            device_name=args.name,
            code=args.code,
            enable_input=args.input,
            enable_clipboard=args.clipboard,
        ))


if __name__ == "__main__":
    main()
