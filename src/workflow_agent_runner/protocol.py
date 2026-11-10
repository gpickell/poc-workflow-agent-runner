"""Messages between the SPA and the runner, sent as JSON text frames.

SPA to runner:
    {"type": "command", "id": str, "command": {"kind": "chat", "text": str}}
    {"type": "interrupt"}
    {"type": "reset"}

Runner to SPA:
    {"type": "status", "state": "idle" | "working"}
    {"type": "command", "id": str, "command": {...}}  -- echo of a received command, for every client
    {"type": "clara", "text": str, "fallback": bool}
    {"type": "turn_end", "id": str, "ok": bool, "durationMs": int, "costUsd": float,
     "tokens": {"input": int, "cacheRead": int, "cacheWrite": int, "output": int}}
    {"type": "error", "message": str, "id"?: str}
    {"type": "reset"}  -- clear the chat; a new session started, or history replay follows

On connect the runner sends "reset", then the current session's command, clara,
turn_end and error messages in order, then "status".

Mirrored in spa/src/protocol.ts.
"""

from __future__ import annotations

import json
from typing import Any


class ProtocolError(Exception):
    pass


def _field(data: dict[str, Any], name: str, kind: type) -> Any:
    value = data.get(name)
    if not isinstance(value, kind):
        raise ProtocolError(f"{name!r} must be a {kind.__name__}")
    return value


def parse_command(command: Any) -> dict[str, Any]:
    """Validate a command and return only its known fields."""
    if not isinstance(command, dict):
        raise ProtocolError("'command' must be an object")
    kind = command.get("kind")
    if kind == "chat":
        return {"kind": "chat", "text": _field(command, "text", str)}
    raise ProtocolError(f"unknown command kind {kind!r}")


def parse(raw: str | bytes) -> dict[str, Any]:
    """Parse and validate one message from the SPA."""
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise ProtocolError(f"not JSON: {e}") from e
    if not isinstance(data, dict):
        raise ProtocolError("message must be an object")
    match data.get("type"):
        case "command":
            return {"type": "command", "id": _field(data, "id", str), "command": parse_command(data.get("command"))}
        case "interrupt" | "reset" as kind:
            return {"type": kind}
        case kind:
            raise ProtocolError(f"unknown message type {kind!r}")


def status(working: bool) -> str:
    return json.dumps({"type": "status", "state": "working" if working else "idle"})


def command(id: str, command: dict[str, Any]) -> str:
    return json.dumps({"type": "command", "id": id, "command": command})


def clara(text: str, fallback: bool) -> str:
    return json.dumps({"type": "clara", "text": text, "fallback": fallback})


def turn_end(id: str, ok: bool, duration_ms: int, cost_usd: float, usage: dict[str, Any] | None) -> str:
    usage = usage or {}
    tokens = {
        "input": usage.get("input_tokens", 0),
        "cacheRead": usage.get("cache_read_input_tokens", 0),
        "cacheWrite": usage.get("cache_creation_input_tokens", 0),
        "output": usage.get("output_tokens", 0),
    }
    return json.dumps({"type": "turn_end", "id": id, "ok": ok, "durationMs": duration_ms,
                       "costUsd": round(cost_usd, 6), "tokens": tokens})


def reset() -> str:
    return json.dumps({"type": "reset"})


def error(message: str, id: str | None = None) -> str:
    data: dict[str, Any] = {"type": "error", "message": message}
    if id is not None:
        data["id"] = id
    return json.dumps(data)
