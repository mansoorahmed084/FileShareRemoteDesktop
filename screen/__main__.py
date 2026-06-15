"""CLI entry point — python -m screen host|view|monitors"""

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
    host_p.add_argument("--scale", type=float, default=1.0, help="Resolution scale 0.25–1.0 (default: 1.0)")
    host_p.add_argument("--input", action="store_true", help="Allow remote mouse/keyboard control")
    host_p.add_argument("--clipboard", action="store_true", help="Enable clipboard sync")

    view_p = sub.add_parser("view", help="View and control a remote screen")
    view_p.add_argument("--server", "-s", required=True, help="Relay server URL (ws://ip:8765)")
    view_p.add_argument("--name", "-n", default="Viewer", help="Device name")
    view_p.add_argument("--code", "-c", default=None, help="6-digit pairing code from host (GUI prompt if omitted)")
    view_p.add_argument("--input", action="store_true", help="Send mouse/keyboard to host")
    view_p.add_argument("--clipboard", action="store_true", help="Enable clipboard sync")

    sub.add_parser("monitors", help="List available monitors")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "monitors":
        from .capture import list_monitors
        monitors = list_monitors()
        print(f"\n  Found {len(monitors)} monitor(s):\n")
        for mon in monitors:
            primary = " (primary)" if mon["primary"] else ""
            print(f"    [{mon['index']}] {mon['width']}x{mon['height']}"
                  f" at ({mon['left']},{mon['top']}){primary}")
        print(f"\n  Use --monitor <index> with the host command.\n")
    elif args.command == "host":
        from .host import run_host
        asyncio.run(run_host(
            server_url=args.server,
            device_name=args.name,
            fps=args.fps,
            monitor=args.monitor,
            scale=max(0.25, min(1.0, args.scale)),
            enable_input=args.input,
            enable_clipboard=args.clipboard,
        ))
    elif args.command == "view":
        code = args.code
        if code is None:
            try:
                from .pairing_gui import ask_pairing_code
                code = ask_pairing_code()
            except Exception:
                code = input("  Enter pairing code: ").strip()
            if not code:
                print("  Cancelled.")
                sys.exit(0)
        from .viewer import run_viewer
        asyncio.run(run_viewer(
            server_url=args.server,
            device_name=args.name,
            code=code,
            enable_input=args.input,
            enable_clipboard=args.clipboard,
        ))


if __name__ == "__main__":
    main()
