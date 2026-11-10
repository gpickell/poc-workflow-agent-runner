"""Command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import shutil
import subprocess
import sys

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
)

from . import server
from .server import DEFAULT_ORIGINS
from .session import Session, describe_error

# verbatim_prompts needs 2.1.248.
MIN_CLAUDE_VERSION = (2, 1, 248)

PROBE_TEXT = (
    "Diagnostic check. List every tool you can call, by exact name. Then say whether "
    "your context contains any CLAUDE.md content, memory files, skills, or instructions "
    "other than this system prompt. Quote the first line of anything you find."
)


class PreflightError(Exception):
    pass


def check_claude(path: str) -> None:
    """Raise PreflightError unless `path` runs a recent enough Claude Code."""
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30).stdout
    except OSError as e:
        raise PreflightError(f"Could not run Claude Code at {path}: {e}") from e
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", out.strip())
    if not match:
        raise PreflightError(f"Could not read the Claude Code version from {path!r}: {out.strip()!r}")
    version = tuple(int(part) for part in match.groups())
    if version < MIN_CLAUDE_VERSION:
        need = ".".join(map(str, MIN_CLAUDE_VERSION))
        have = ".".join(map(str, version))
        raise PreflightError(f"Claude Code {have} is too old; {need} or later is needed. Run `claude update`.")


def resolve_claude(choice: str | None) -> str | None:
    """Return the Claude Code executable to run, or None for the SDK's bundled copy.

    An explicit --claude path must work. Otherwise the installed `claude` is
    preferred, falling back to the bundled copy if it is missing or too old.
    """
    if choice == "bundled":
        return None
    if choice:
        check_claude(choice)
        return choice
    path = shutil.which("claude")
    if not path:
        print("note: Claude Code is not on PATH; using the copy bundled with the Agent SDK.", file=sys.stderr)
        return None
    try:
        check_claude(path)
    except PreflightError as e:
        print(f"note: {e} Using the copy bundled with the Agent SDK.", file=sys.stderr)
        return None
    return path


def print_event(message: object) -> None:
    if isinstance(message, SystemMessage) and message.subtype == "init":
        data = message.data
        print("[init]")
        for key in ("claude_code_version", "model", "cwd", "permissionMode", "apiKeySource",
                    "tools", "mcp_servers", "skills", "plugins", "slash_commands", "agents"):
            print(f"  {key}: {json.dumps(data.get(key))}")
    elif isinstance(message, SystemMessage):
        print(f"[system:{message.subtype}]")
    elif isinstance(message, AssistantMessage):
        if message.error:
            print(f"[error] {describe_error(message.error)}")
            return
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"[assistant] {block.text}")
            elif isinstance(block, ToolUseBlock):
                print(f"[tool_use] {block.name} {json.dumps(block.input)}")
    elif isinstance(message, UserMessage):
        print("[tool_result]")
    elif isinstance(message, ResultMessage):
        print(f"[result] {message.subtype} error={message.is_error} turns={message.num_turns} "
              f"ms={message.duration_ms} cost={message.total_cost_usd} session={message.session_id}")
        if message.usage:
            print(f"  usage: {json.dumps(message.usage)}")
        if message.permission_denials:
            print(f"  denials: {json.dumps(message.permission_denials)}")
        if message.errors:
            print(f"  errors: {message.errors}")


async def show_clara(text: str, fallback: bool) -> None:
    print(f"[clara{':fallback' if fallback else ''}] {text}")


async def probe(cli_path: str | None, text: str) -> None:
    async with Session(cli_path, show_clara) as session:
        async for message in session.send({"kind": "chat", "text": text}):
            print_event(message)


async def chat(cli_path: str | None) -> None:
    """Read Clara's messages from stdin, one per line, in a single session."""
    turns = fallbacks = 0
    cost = 0.0

    async def on_clara(text: str, fallback: bool) -> None:
        nonlocal fallbacks
        fallbacks += fallback
        await show_clara(text, fallback)

    async with Session(cli_path, on_clara) as session:
        loop = asyncio.get_running_loop()
        while line := await loop.run_in_executor(None, sys.stdin.readline):
            if not (text := line.strip()):
                continue
            print(f"[you] {text}")
            async for message in session.send({"kind": "chat", "text": text}):
                if isinstance(message, AssistantMessage) and message.error:
                    print_event(message)
                elif isinstance(message, ResultMessage):
                    # total_cost_usd is the session total so far, not this turn's.
                    turns += 1
                    total = message.total_cost_usd or cost
                    print(f"[turn] {message.duration_ms} ms, ${total - cost:.4f}")
                    cost = total
    print(f"[done] {turns} turns, {fallbacks} fallbacks, ${cost:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="workflow-agent-runner")
    parser.add_argument("--claude", help='Claude Code executable, or "bundled" for the SDK\'s copy. '
                                         "Defaults to `claude` on PATH, falling back to the bundled copy.")
    sub = parser.add_subparsers(dest="cmd")
    serve_cmd = sub.add_parser("serve", help="Serve the SPA's WebSocket (the default).")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8787)
    serve_cmd.add_argument("--origin", action="append", dest="origins",
                           help=f"Allowed page origin; repeatable. Default: {', '.join(DEFAULT_ORIGINS)}")
    probe_cmd = sub.add_parser("probe", help="Send one command and print every event.")
    probe_cmd.add_argument("--text", default=PROBE_TEXT)
    sub.add_parser("chat", help="Chat as Clara from the terminal, one message per line.")
    args = parser.parse_args()
    if args.cmd is None:
        args = parser.parse_args([*sys.argv[1:], "serve"])

    try:
        cli_path = resolve_claude(args.claude)
    except PreflightError as e:
        sys.exit(f"error: {e}")
    print(f"claude: {cli_path or 'bundled with the Agent SDK'}")

    if args.cmd == "probe":
        asyncio.run(probe(cli_path, args.text))
    elif args.cmd == "chat":
        asyncio.run(chat(cli_path))
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
        try:
            asyncio.run(server.run(cli_path, args.host, args.port, args.origins or DEFAULT_ORIGINS))
        except KeyboardInterrupt:
            pass
