"""WebSocket server relaying between the SPA and one Claude Code session."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from claude_agent_sdk import AssistantMessage, ResultMessage
from websockets.asyncio.server import ServerConnection, broadcast, serve

from . import protocol
from .session import Session, describe_error
from .transcript import Transcript

log = logging.getLogger(__name__)

# The Vite dev server's default address.
DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


class Runner:
    """Owns the session. Commands run one at a time, in the order received."""

    def __init__(self, cli_path: str | None) -> None:
        self._cli_path = cli_path
        self._clients: set[ServerConnection] = set()
        self._queue: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
        self._turn = asyncio.Lock()
        self._generation = 0  # bumped on reset; queued commands from before are dropped
        self._working = False
        self._cost = 0.0
        self._session: Session | None = None
        self._transcript: Transcript | None = None
        # The current session's command, clara, turn_end and error messages,
        # replayed to clients that connect later.
        self._history: list[str] = []

    def _broadcast(self, message: str) -> None:
        broadcast(self._clients, message)

    def _publish(self, message: str) -> None:
        self._history.append(message)
        self._broadcast(message)

    def _set_working(self, working: bool) -> None:
        self._working = working
        self._broadcast(protocol.status(working))

    async def _on_clara(self, text: str, fallback: bool) -> None:
        if self._transcript:
            self._transcript.write("clara", text=text, fallback=fallback)
        self._publish(protocol.clara(text, fallback))

    async def _open_session(self) -> None:
        self._transcript = Transcript()
        log.info("transcript: %s", self._transcript.path)
        self._session = Session(self._cli_path, self._on_clara)
        await self._session.connect()
        self._cost = 0.0
        self._history = []

    async def _close_session(self) -> None:
        if self._session:
            await self._session.disconnect()
        if self._transcript:
            self._transcript.close()

    async def start(self) -> None:
        await self._open_session()
        asyncio.create_task(self._worker())

    async def stop(self) -> None:
        await self._close_session()

    async def _worker(self) -> None:
        while True:
            generation, id, command = await self._queue.get()
            async with self._turn:
                if generation != self._generation:
                    continue
                self._set_working(True)
                try:
                    await self._run_turn(id, command)
                except Exception as e:
                    log.exception("turn %s failed", id)
                    self._publish(protocol.error(f"Turn failed: {e}", id))
                finally:
                    self._set_working(False)

    async def _run_turn(self, id: str, command: dict[str, Any]) -> None:
        assert self._session and self._transcript
        log.info("turn %s: %s", id, command)
        self._transcript.write("command", id=id, command=command)
        async for message in self._session.send(command):
            self._transcript.sdk(message)
            if isinstance(message, AssistantMessage) and message.error:
                self._publish(protocol.error(describe_error(message.error), id))
            elif isinstance(message, ResultMessage):
                # total_cost_usd is the session total so far, not this turn's; usage is per turn.
                total = message.total_cost_usd or self._cost
                cost, self._cost = total - self._cost, total
                log.info("turn %s ended: %s, %d ms, $%.4f", id, message.subtype, message.duration_ms, cost)
                if message.permission_denials:
                    # Nothing should ask: unlisted tools are absent, and dontAsk denies the rest.
                    log.warning("turn %s: permission denials: %s", id, message.permission_denials)
                self._publish(protocol.turn_end(id, not message.is_error, message.duration_ms, cost, message.usage))

    async def _interrupt(self) -> None:
        if self._working and self._session:
            log.info("interrupting")
            if self._transcript:
                self._transcript.write("interrupt")
            await self._session.interrupt()

    async def _reset(self) -> None:
        log.info("resetting session")
        self._generation += 1
        await self._interrupt()
        async with self._turn:
            await self._close_session()
            await self._open_session()
        self._broadcast(protocol.reset())

    async def handle(self, ws: ServerConnection) -> None:
        log.info("client connected from %s", ws.request.headers.get("Origin") if ws.request else None)
        # Replay without awaiting, so no broadcast can slip in between or out of order.
        for message in [protocol.reset(), *self._history, protocol.status(self._working)]:
            broadcast([ws], message)
        self._clients.add(ws)
        try:
            async for raw in ws:
                try:
                    message = protocol.parse(raw)
                except protocol.ProtocolError as e:
                    await ws.send(protocol.error(f"Bad message: {e}"))
                    continue
                match message["type"]:
                    case "command":
                        self._publish(protocol.command(message["id"], message["command"]))
                        self._queue.put_nowait((self._generation, message["id"], message["command"]))
                    case "interrupt":
                        await self._interrupt()
                    case "reset":
                        await self._reset()
        finally:
            self._clients.discard(ws)
            log.info("client disconnected")


async def run(cli_path: str | None, host: str, port: int, origins: list[str]) -> None:
    runner = Runner(cli_path)
    await runner.start()
    try:
        async with serve(runner.handle, host, port, origins=origins) as server:
            log.info("listening on ws://%s:%d for %s", host, port, ", ".join(origins))
            await server.serve_forever()
    finally:
        await runner.stop()
