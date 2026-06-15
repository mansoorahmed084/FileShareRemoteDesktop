#!/usr/bin/env python3
"""
RemoteDesktop MCP Server

Exposes tools for AI agents (Claude, etc.) to send/receive files and text
between paired devices via the RemoteDesktop relay server.

Run standalone:
  python mcp_server.py --server ws://localhost:8765 --name "Agent Device"

Configure in Claude Desktop (claude_desktop_config.json):
  {
    "mcpServers": {
      "remote-desktop": {
        "command": "python",
        "args": ["/path/to/cli/mcp_server.py", "--server", "ws://192.168.1.42:8765"]
      }
    }
  }

Configure in Claude Code (settings.json):
  {
    "mcpServers": {
      "remote-desktop": {
        "command": "python",
        "args": ["/path/to/cli/mcp_server.py", "--server", "ws://192.168.1.42:8765"]
      }
    }
  }
"""

import argparse
import asyncio
import json
import sys
import time
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from client import RemoteDesktopClient, load_config

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-remote-desktop")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", "-s", default=None, help="Relay server URL")
    parser.add_argument("--name", "-n", default="MCP Agent", help="Device name")
    return parser.parse_args()


app = Server("remote-desktop")
client = RemoteDesktopClient()
_connected = False
_args = None


async def ensure_connected() -> None:
    global _connected, _args
    if _args is None:
        _args = parse_args()
    if not _connected or not client.state.connected:
        server_url = _args.server or load_config().get("server_url", "ws://localhost:8765")
        device_name = _args.name
        await client.connect(server_url, device_name)
        _connected = True
        await asyncio.sleep(0.5)


def resolve_device(query: str) -> str | None:
    for did, dev in client.state.paired_devices.items():
        if did == query or did.startswith(query) or dev.device_name.lower() == query.lower():
            return did
    return query if len(query) > 8 else None


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="rd_list_devices",
            description="List all paired devices and their online/offline status.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="rd_send_text",
            description="Send text content to a paired device. Use for sharing env variables, code snippets, configs, or any text. The device can be specified by ID, ID prefix, or device name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Device ID, ID prefix, or device name",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content to send",
                    },
                },
                "required": ["device", "text"],
            },
        ),
        Tool(
            name="rd_send_file",
            description="Send a file to a paired device. Provide the absolute file path. Files up to 100MB are supported.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Device ID, ID prefix, or device name",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the file to send",
                    },
                },
                "required": ["device", "file_path"],
            },
        ),
        Tool(
            name="rd_send_env_file",
            description="Read a .env file and send its contents as text to a paired device. Convenient for sharing environment variables between machines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Device ID, ID prefix, or device name",
                    },
                    "env_path": {
                        "type": "string",
                        "description": "Path to the .env file",
                    },
                },
                "required": ["device", "env_path"],
            },
        ),
        Tool(
            name="rd_get_messages",
            description="Get recent text messages received from paired devices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of messages to return (default 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="rd_get_received_files",
            description="List files that have been received from paired devices.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="rd_save_received_file",
            description="Save a received file to disk. Use get_received_files first to get the file ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the received file (from rd_get_received_files)",
                    },
                    "dest_path": {
                        "type": "string",
                        "description": "Directory or full path to save the file to",
                    },
                },
                "required": ["file_id", "dest_path"],
            },
        ),
        Tool(
            name="rd_pair_create",
            description="Generate a 6-digit pairing code. The other device must enter this code within 60 seconds.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="rd_pair_join",
            description="Join a device using a 6-digit pairing code from the other device.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "6-digit pairing code",
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="rd_get_status",
            description="Get current connection status, device ID, and server info.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        await ensure_connected()
    except Exception as e:
        return [TextContent(type="text", text=f"Connection failed: {e}")]

    match name:
        case "rd_list_devices":
            devices = client.list_devices()
            if not devices:
                return [TextContent(type="text", text="No paired devices. Use rd_pair_create or rd_pair_join first.")]
            lines = []
            for d in devices:
                status = "online" if d.is_online else "offline"
                lines.append(f"- {d.device_name} ({d.device_id[:16]}...) [{status}]")
            return [TextContent(type="text", text="\n".join(lines))]

        case "rd_send_text":
            target = resolve_device(arguments["device"])
            if not target:
                return [TextContent(type="text", text=f"Device not found: {arguments['device']}")]
            ok = await client.send_text(target, arguments["text"])
            return [TextContent(type="text", text=f"Sent to {target[:16]}." if ok else "Failed to send.")]

        case "rd_send_file":
            target = resolve_device(arguments["device"])
            if not target:
                return [TextContent(type="text", text=f"Device not found: {arguments['device']}")]
            try:
                await client.send_file(target, arguments["file_path"])
                return [TextContent(type="text", text=f"File sent: {arguments['file_path']}")]
            except FileNotFoundError:
                return [TextContent(type="text", text=f"File not found: {arguments['file_path']}")]

        case "rd_send_env_file":
            target = resolve_device(arguments["device"])
            if not target:
                return [TextContent(type="text", text=f"Device not found: {arguments['device']}")]
            env_path = Path(arguments["env_path"])
            if not env_path.exists():
                return [TextContent(type="text", text=f"File not found: {arguments['env_path']}")]
            content = env_path.read_text()
            ok = await client.send_text(target, content)
            lines_count = content.strip().count("\n") + 1
            return [TextContent(type="text", text=f"Sent {lines_count} env variables to {target[:16]}." if ok else "Failed.")]

        case "rd_get_messages":
            limit = arguments.get("limit", 20)
            msgs = client.get_messages(limit)
            if not msgs:
                return [TextContent(type="text", text="No messages received yet.")]
            lines = []
            for m in msgs:
                ts = time.strftime("%H:%M:%S", time.localtime(m.timestamp))
                preview = m.text[:200] + ("..." if len(m.text) > 200 else "")
                lines.append(f"[{ts}] from {m.from_device[:12]}: {preview}")
            return [TextContent(type="text", text="\n".join(lines))]

        case "rd_get_received_files":
            files = client.get_received_files()
            if not files:
                return [TextContent(type="text", text="No files received yet.")]
            lines = []
            for f in files:
                lines.append(f"- {f.file_name} ({f.file_size:,} bytes) [id: {f.id[:16]}] from {f.from_device[:12]}")
            return [TextContent(type="text", text="\n".join(lines))]

        case "rd_save_received_file":
            try:
                path = client.save_received_file(arguments["file_id"], arguments["dest_path"])
                return [TextContent(type="text", text=f"File saved to: {path}")]
            except ValueError as e:
                return [TextContent(type="text", text=str(e))]

        case "rd_pair_create":
            code = await client.pair_create()
            return [TextContent(type="text", text=f"Pairing code: {code}\nEnter this on the other device within 60 seconds.")]

        case "rd_pair_join":
            result = await client.pair_join(arguments["code"])
            if result:
                dev = client.state.paired_devices.get(result)
                dname = dev.device_name if dev else "Unknown"
                return [TextContent(type="text", text=f"Paired with {dname} ({result[:16]}...)")]
            return [TextContent(type="text", text="Pairing failed — invalid or expired code.")]

        case "rd_get_status":
            info = {
                "connected": client.state.connected,
                "server_url": client.state.server_url,
                "device_id": client.state.device_id,
                "device_name": client.state.device_name,
                "paired_devices": len(client.state.paired_devices),
                "pending_messages": len(client.state.messages),
                "received_files": len(client.state.received_files),
            }
            return [TextContent(type="text", text=json.dumps(info, indent=2))]

        case _:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    global _args
    _args = parse_args()
    logger.info("Starting RemoteDesktop MCP server...")

    async with stdio_server() as (read_stream, write_stream):
        init_options = app.create_initialization_options()
        await app.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
