#!/usr/bin/env python3
"""
RemoteDesktop CLI — share text and files from the terminal.

Usage:
  rdcli connect [--server URL] [--name NAME]
  rdcli status
  rdcli devices
  rdcli pair create
  rdcli pair join <code>
  rdcli send <device> <text>
  rdcli send-file <device> <path>
  rdcli send-env <device> <env-file>
  rdcli listen
"""

import asyncio
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from client import RemoteDesktopClient, load_config, ReceivedMessage, ReceivedFile

console = Console()


def get_default_server() -> str:
    return load_config().get("server_url", "ws://localhost:8765")


def get_default_name() -> str:
    return load_config().get("device_name", "CLI Device")


@click.group()
def cli():
    """RemoteDesktop CLI — share text and files between devices."""
    pass


@cli.command()
@click.option("--server", "-s", default=None, help="Server URL (e.g., ws://192.168.1.42:8765)")
@click.option("--name", "-n", default=None, help="Device name")
def connect(server: str | None, name: str | None):
    """Connect to relay server and listen for messages."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()

        client.on("text", lambda msg: _print_text(msg))
        client.on("file_complete", lambda f: _print_file_received(f))
        client.on("device_online", lambda did: console.print(f"  [green]+ Device online:[/] {did[:12]}"))
        client.on("device_offline", lambda did: console.print(f"  [red]- Device offline:[/] {did[:12]}"))
        client.on("error", lambda e: console.print(f"  [red]Error:[/] {e}"))

        console.print(f"\n  Connecting to [cyan]{server}[/] as [yellow]{name}[/]...")
        await client.connect(server, name)
        console.print(f"  [green]Connected![/] Device ID: [dim]{client.state.device_id[:16]}...[/]")
        console.print(f"  Listening for messages. Press Ctrl+C to stop.\n")

        try:
            while client.state.connected:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await client.disconnect()
            console.print("\n  Disconnected.")

    asyncio.run(_run())


@cli.command()
def status():
    """Show connection config and device ID."""
    config = load_config()
    table = Table(title="RemoteDesktop Status", show_header=False)
    table.add_column("Key", style="dim")
    table.add_column("Value")
    table.add_row("Device ID", config.get("device_id", "Not set")[:16] + "...")
    table.add_row("Server", config.get("server_url", "Not configured"))
    table.add_row("Device Name", config.get("device_name", "Not set"))
    table.add_row("Config", str(load_config.__code__.co_filename).replace("client.py", ""))
    console.print(table)


@cli.group()
def pair():
    """Pair with another device."""
    pass


@pair.command("create")
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
def pair_create(server: str | None, name: str | None):
    """Generate a 6-digit pairing code."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()
        await client.connect(server, name)
        code = await client.pair_create()
        console.print(Panel(
            f"[bold cyan]{code}[/]",
            title="Pairing Code",
            subtitle="Enter this on the other device (expires in 60s)",
            width=40,
        ))
        console.print("  Waiting for pair to complete...")

        for _ in range(600):
            await asyncio.sleep(0.1)
            if client.state.paired_devices:
                did = list(client.state.paired_devices.keys())[-1]
                dev = client.state.paired_devices[did]
                console.print(f"\n  [green]Paired with {dev.device_name}[/] ({did[:12]}...)")
                await client.disconnect()
                return
        console.print("  [red]Timed out waiting for pair.[/]")
        await client.disconnect()

    asyncio.run(_run())


@pair.command("join")
@click.argument("code")
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
def pair_join(code: str, server: str | None, name: str | None):
    """Join a device using a 6-digit code."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()
        await client.connect(server, name)
        result = await client.pair_join(code)
        if result:
            dev = client.state.paired_devices.get(result)
            dname = dev.device_name if dev else "Unknown"
            console.print(f"\n  [green]Paired with {dname}[/] ({result[:12]}...)")
        else:
            console.print("  [red]Pairing failed — invalid or expired code.[/]")
        await client.disconnect()

    asyncio.run(_run())


@cli.command()
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
def devices(server: str | None, name: str | None):
    """List paired/online devices."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()
        await client.connect(server, name)
        await asyncio.sleep(1)

        devs = client.list_devices()
        if not devs:
            console.print("  No paired devices found.")
        else:
            table = Table(title="Paired Devices")
            table.add_column("ID", style="dim")
            table.add_column("Name")
            table.add_column("Status")
            for d in devs:
                status_str = "[green]Online[/]" if d.is_online else "[red]Offline[/]"
                table.add_row(d.device_id[:16] + "...", d.device_name, status_str)
            console.print(table)
        await client.disconnect()

    asyncio.run(_run())


@cli.command()
@click.argument("device")
@click.argument("text")
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
def send(device: str, text: str, server: str | None, name: str | None):
    """Send text to a paired device. DEVICE can be a full ID or prefix."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()
        await client.connect(server, name)
        await asyncio.sleep(0.5)

        target = _resolve_device(client, device)
        if not target:
            console.print(f"  [red]Device not found:[/] {device}")
            await client.disconnect()
            return

        ok = await client.send_text(target, text)
        if ok:
            console.print(f"  [green]Sent[/] to {target[:12]}...")
        else:
            console.print("  [red]Failed to send.[/]")
        await client.disconnect()

    asyncio.run(_run())


@cli.command("send-file")
@click.argument("device")
@click.argument("path", type=click.Path(exists=True))
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
def send_file(device: str, path: str, server: str | None, name: str | None):
    """Send a file to a paired device."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()

        def on_progress(data):
            pct = int(data["chunk"] / data["total"] * 100)
            console.print(f"  [{pct}%] {data['file_name']} — chunk {data['chunk']}/{data['total']}", end="\r")

        client.on("file_progress", on_progress)
        await client.connect(server, name)
        await asyncio.sleep(0.5)

        target = _resolve_device(client, device)
        if not target:
            console.print(f"  [red]Device not found:[/] {device}")
            await client.disconnect()
            return

        console.print(f"  Sending [cyan]{path}[/]...")
        await client.send_file(target, path)
        console.print(f"\n  [green]File sent![/]")
        await client.disconnect()

    asyncio.run(_run())


@cli.command("send-env")
@click.argument("device")
@click.argument("env_file", type=click.Path(exists=True))
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
def send_env(device: str, env_file: str, server: str | None, name: str | None):
    """Send a .env file as text (for quick copy-paste on the other side)."""
    server = server or get_default_server()
    name = name or get_default_name()

    from pathlib import Path
    content = Path(env_file).read_text()

    async def _run():
        client = RemoteDesktopClient()
        await client.connect(server, name)
        await asyncio.sleep(0.5)

        target = _resolve_device(client, device)
        if not target:
            console.print(f"  [red]Device not found:[/] {device}")
            await client.disconnect()
            return

        ok = await client.send_text(target, content)
        if ok:
            lines = content.strip().count("\n") + 1
            console.print(f"  [green]Sent {lines} env variables[/] to {target[:12]}...")
        await client.disconnect()

    asyncio.run(_run())


@cli.command()
@click.option("--server", "-s", default=None)
@click.option("--name", "-n", default=None)
@click.option("--save-dir", "-d", default=".", help="Directory to save received files")
def listen(server: str | None, name: str | None, save_dir: str):
    """Listen for incoming messages and files."""
    server = server or get_default_server()
    name = name or get_default_name()

    async def _run():
        client = RemoteDesktopClient()

        client.on("text", lambda msg: _print_text(msg))
        client.on("device_online", lambda did: console.print(f"  [green]+ Device online:[/] {did[:12]}"))
        client.on("device_offline", lambda did: console.print(f"  [red]- Device offline:[/] {did[:12]}"))
        client.on("error", lambda e: console.print(f"  [red]Error:[/] {e}"))

        def on_file(rf: ReceivedFile):
            dest = client.save_received_file(rf.id, save_dir)
            console.print(f"  [green]File saved:[/] {dest} ({rf.file_size:,} bytes)")

        client.on("file_complete", on_file)

        console.print(f"\n  Connecting to [cyan]{server}[/]...")
        await client.connect(server, name)
        console.print(f"  [green]Connected![/] Listening... (Ctrl+C to stop)")
        console.print(f"  Files will be saved to: [cyan]{save_dir}[/]\n")

        try:
            while client.state.connected:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await client.disconnect()

    asyncio.run(_run())


def _resolve_device(client: RemoteDesktopClient, query: str) -> str | None:
    """Resolve a device ID or prefix to a full device ID."""
    for did in client.state.paired_devices:
        if did == query or did.startswith(query):
            return did
    for did in client.state.paired_devices:
        dev = client.state.paired_devices[did]
        if dev.device_name.lower() == query.lower():
            return did
    return query if len(query) > 8 else None


def _print_text(msg: ReceivedMessage):
    ts = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
    console.print(f"  [dim]{ts}[/] [cyan]{msg.from_device[:12]}[/] → {msg.text}")


def _print_file_received(rf: ReceivedFile):
    console.print(f"  [green]File received:[/] {rf.file_name} ({rf.file_size:,} bytes) from {rf.from_device[:12]}")


import time  # noqa: E402 (already imported above but keeping for clarity)

if __name__ == "__main__":
    cli()
