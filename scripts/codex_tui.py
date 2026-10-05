#!/usr/bin/env python3
"""Call installed codex_tui tools through a live local TUI context."""

import argparse
import json
import os
from pathlib import Path
import sys
import time


class NativeToolError(RuntimeError):
    """The native tool returned an explicit error."""


class DeliveryUnknown(RuntimeError):
    """A send attempt has no verified acknowledgment."""


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-thread", required=True, help="Live sender-capable TUI context ID")
    parser.add_argument("--socket", type=Path, help="Local Codex app-server control socket")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    for name in ("list", "archived"):
        command = commands.add_parser(name)
        command.add_argument("--limit", type=int, default=50)
        if name == "archived":
            command.add_argument("--cursor", help="Opaque cursor from the native result")
    read = commands.add_parser("read")
    read.add_argument("--thread", required=True)
    read.add_argument("--turn-limit", type=int, default=5)
    read.add_argument("--cursor", help="Opaque cursor from the native result")
    send = commands.add_parser("send")
    send.add_argument("--thread", required=True)
    send.add_argument("--message-file", type=Path, required=True)
    return parser.parse_args()


def rpc(ws, request_id, method, params, timeout=30):
    ws.send(json.dumps({"jsonrpc": "2.0", "id": request_id,
                        "method": method, "params": params}))
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{method} timed out")
        raw = ws.recv(timeout=remaining)
        if raw is None:
            raise ConnectionError("Local control connection closed")
        response = json.loads(raw)
        if not isinstance(response, dict):
            raise ValueError("Invalid JSON-RPC response")
        if response.get("id") != request_id:
            continue
        if "error" in response:
            raise RuntimeError(json.dumps(response["error"], ensure_ascii=False))
        return response["result"]


def tool_call(ws, context, request_id, name, arguments, timeout=30):
    result = rpc(ws, request_id, "mcpServer/tool/call",
                 {"threadId": context, "server": "codex_tui",
                  "tool": name, "arguments": arguments}, timeout=timeout)
    if result.get("isError"):
        raise NativeToolError(json.dumps(result, ensure_ascii=False))
    return result


def context_tools(ws, context):
    status = rpc(ws, 2, "mcpServerStatus/list",
                 {"threadId": context, "serverName": "codex_tui", "detail": "full"})
    servers = [s for s in status.get("data", []) if s.get("name") == "codex_tui"]
    if len(servers) != 1 or servers[0].get("runtimeStatus") != "connected":
        raise RuntimeError("codex_tui is not connected in the selected TUI context")
    return servers[0].get("tools", {})


def read_prompt(path, tool):
    data = path.read_bytes()
    prompt = data.decode("utf-8")
    schema = tool.get("inputSchema", {}).get("properties", {}).get("prompt", {})
    limit = schema.get("maxLength")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("Cannot determine the prompt limit from the live schema")
    if not prompt.strip() or len(data) > limit:
        raise ValueError(f"Message must be nonblank and at most {limit} UTF-8 bytes")
    return prompt


def acknowledged_recipient(result):
    structured = result.get("structuredContent")
    recipients = []
    if isinstance(structured, dict) and isinstance(structured.get("threadId"), str):
        recipients.append(structured["threadId"])
    for item in result.get("content", []):
        if item.get("type") != "text":
            continue
        try:
            payload = json.loads(item["text"])
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("threadId"), str):
            recipients.append(payload["threadId"])
    if recipients and len(set(recipients)) == 1:
        return recipients[0]
    return None


def send_handoff(ws, context, recipient, prompt):
    try:
        result = tool_call(ws, context, 3, "send_message_to_thread",
                           {"threadId": recipient, "prompt": prompt}, timeout=45)
        acknowledged = acknowledged_recipient(result)
    except NativeToolError:
        raise
    except (Exception, KeyboardInterrupt) as exc:
        raise DeliveryUnknown(
            "Send lost its acknowledgment; delivery is UNKNOWN. "
            "Read the recipient thread before retrying."
        ) from exc
    if acknowledged != recipient:
        raise DeliveryUnknown(
            "Native response did not confirm the intended recipient; delivery is UNKNOWN. "
            "Inspect recipient activity before retrying."
        )
    return {"senderAccepted": True, "recipientThreadId": recipient,
            "recipientActionVerified": False}


def run(ws, args):
    rpc(ws, 1, "initialize",
        {"clientInfo": {"name": "codex-thread-coordination", "version": "1.0"},
         "capabilities": {"experimentalApi": True}})
    ws.send(json.dumps({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
    tools = context_tools(ws, args.context_thread)
    if args.command == "status":
        return {"status": "connected", "tools": tools}
    name = {"list": "list_threads", "archived": "list_archived_threads",
            "read": "read_thread", "send": "send_message_to_thread"}[args.command]
    if name not in tools:
        raise RuntimeError(f"codex_tui.{name} is unavailable in the selected context")
    if args.command == "send":
        prompt = read_prompt(args.message_file, tools[name])
        return send_handoff(ws, args.context_thread, args.thread, prompt)
    if args.command in ("list", "archived"):
        arguments = {"limit": args.limit}
    else:
        arguments = {"threadId": args.thread, "turnLimit": args.turn_limit}
    if getattr(args, "cursor", None):
        arguments["cursor"] = args.cursor
    return tool_call(ws, args.context_thread, 3, name, arguments)


def main():
    args = parse_args()
    try:
        from websockets.sync.client import unix_connect
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt to use the optional local helper") from exc
    codex_dir = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    socket = args.socket or codex_dir / "app-server-control/app-server-control.sock"
    with unix_connect(str(socket), open_timeout=5, close_timeout=2,
                      max_size=8 * 1024 * 1024) as ws:
        result = run(ws, args)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"codex_tui recovery failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
