"""MCP tools hosted in the runner's own process."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

SERVER = "clara"
TALK_AT_CLARA = f"mcp__{SERVER}__talk_at_clara"


def clara_server(show: Callable[[str], Awaitable[None]]) -> McpSdkServerConfig:
    """Tools for reaching Clara. `show` delivers text to her screen."""

    @tool(
        "talk_at_clara",
        "Show a message to Clara. This is the only way she sees anything you write. "
        "Call it once per turn with your full reply; call it again only for separate updates.",
        {"text": Annotated[str, "Markdown to show Clara."]},
    )
    async def talk_at_clara(args: dict[str, Any]) -> dict[str, Any]:
        await show(args["text"])
        return {"content": [{"type": "text", "text": "Shown to Clara. Don't send it again."}]}

    return create_sdk_mcp_server(SERVER, tools=[talk_at_clara])
