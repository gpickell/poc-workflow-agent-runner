"""A Claude Code session driven through the Agent SDK."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from importlib import resources
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, Message, ResultMessage

from .tools import SERVER, TALK_AT_CLARA, clara_server

# Claude Code runs here. A fixed folder keeps sessions resumable, since Claude
# Code stores transcripts by working directory.
WORKSPACE = Path.home() / ".workflow-agent-runner" / "workspace"

# Built-in Claude Code tools the runner allows. Everything else stays off.
BUILTIN_TOOLS = ["WebSearch"]

# Receives text for Clara. The flag is True when it is the turn's final text,
# shown because Claude ended the turn without calling talk_at_clara.
ClaraHandler = Callable[[str, bool], Awaitable[None]]


def describe_error(error: str) -> str:
    """A readable message for AssistantMessage.error."""
    if error == "authentication_failed":
        return "Claude Code is not signed in. Run `claude` and sign in, then try again."
    return f"Claude Code reported an error: {error}"


def system_prompt() -> str:
    return resources.files(__package__).joinpath("system_prompt.md").read_text(encoding="utf-8")


def format_command(command: dict[str, Any]) -> str:
    return f"<command>{json.dumps(command)}</command>"


class Session:
    def __init__(self, cli_path: str | None, on_clara: ClaraHandler) -> None:
        self._on_clara = on_clara
        self._spoke = False
        self._client = ClaudeSDKClient(self._options(cli_path))

    def _options(self, cli_path: str | None) -> ClaudeAgentOptions:
        """Options for a runner-owned boot: only what the runner supplies is loaded."""
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        return ClaudeAgentOptions(
            cli_path=cli_path,  # None means the SDK's bundled copy
            cwd=WORKSPACE,
            system_prompt=system_prompt(),
            setting_sources=[],  # None would load user, project and local settings
            strict_mcp_config=True,
            mcp_servers={SERVER: clara_server(self._show)},
            tools=BUILTIN_TOOLS,
            allowed_tools=[*BUILTIN_TOOLS, TALK_AT_CLARA],
            skills=[],
            permission_mode="dontAsk",
            verbatim_prompts=True,  # no @file expansion or slash commands in commands
        )

    async def _show(self, text: str) -> None:
        self._spoke = True
        await self._on_clara(text, False)

    async def connect(self) -> None:
        await self._client.connect()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def __aenter__(self) -> Session:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    async def send(self, command: dict[str, Any]) -> AsyncIterator[Message]:
        """Send one command and yield events until the turn ends."""
        self._spoke = False
        await self._client.query(format_command(command))
        async for message in self._client.receive_response():
            if isinstance(message, ResultMessage) and not self._spoke and not message.is_error and message.result:
                await self._on_clara(message.result, True)
            yield message

    async def interrupt(self) -> None:
        await self._client.interrupt()
