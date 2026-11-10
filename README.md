# Workflow Agent Runner (PoC)

A web app drives the user's own Claude Code as its AI engine.

```
SPA (browser, Vite)  <-- WebSocket -->  Runner (Python)  <-- Agent SDK -->  Claude Code (yours)
                                        - hosts the app's MCP tools
                                        - owns the Claude Code boot
                                        - relays commands and replies
```

- **The runner is the user.** Each chat message goes to Claude Code as a structured user message (`<command>{...}</command>`). Claude ends its turn normally. No polling tool, no Stop hook.
- **Claude only talks through a tool.** Clara, the persona using the app, sees only what Claude sends with `talk_at_clara`. If a turn ends without it, the runner shows Claude's final text and marks it "fallback".
- **Locked down.** None of your Claude Code settings, CLAUDE.md, memory, hooks or MCP servers are loaded. Claude has two tools, `talk_at_clara` and `WebSearch`; no shell, files or web fetch. There are no permission prompts: anything not allowed is denied silently.

See [PLAN.md](PLAN.md) for the background, decisions and findings.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Node.js 20.19+ or 22.12+ (Vite 8)
- [Claude Code](https://claude.com/claude-code), signed in (run `claude` once). Version 2.1.248 or later. If it is missing or too old, the runner falls back to the copy bundled with the Agent SDK.

## Run it

Two terminals, from the repo root:

```sh
# 1. Runner: WebSocket on ws://127.0.0.1:8787
uv run workflow-agent-runner
```

```sh
# 2. SPA: http://localhost:5173
cd spa
npm install
npm run dev
```

Open http://localhost:5173. The chip in the top right should say **Runner connected**.

The first run of `uv run` downloads the Agent SDK, about 150 MB, because it bundles Claude Code.

## Demo script

About 10 minutes. Each step shows one property of the design.

1. **It's connected.** Point out the **Runner connected** chip. Stop the runner (Ctrl+C): the chip turns to **Runner offline** and Send is disabled. Start it again: the page reconnects by itself within a few seconds.
2. **Plain chat.** Ask *"What can you do?"*. The reply comes through `talk_at_clara`; the runner terminal logs the turn. The caption under the input shows time, cost and tokens.
3. **Rich replies.** Ask *"Give me a two-item bullet list of map types, with the names in bold."* Replies are Markdown.
4. **Web search.** Ask *"Search the web: what's the newest ArcGIS Maps SDK for JavaScript release? Include sources."* It takes about 10 s. Source links open in a new tab. Point out the higher cost on the caption.
5. **Stop.** Ask *"Write a 1500-word essay on the history of cartography."*, then press the red **Stop** button. The turn ends at once and the chat says "Stopped."
6. **Memory within a session.** Ask *"What was the first thing I asked you?"*
7. **Shared view.** Open a second tab on http://localhost:5173. It replays the same conversation, and new messages appear in both.
8. **Locked down.** Ask *"Read C:\Windows\win.ini and tell me its first line."* Claude can't: no file tool exists. Ask *"Run `dir` for me."*: same, no shell.
9. **New chat.** Press **New chat**. The runner starts a fresh Claude Code session (about 2.5 s) and every tab clears. Ask *"What was the first thing I asked you?"*: it doesn't know.
10. **Transcripts.** Open the newest file in `~/.workflow-agent-runner/transcripts/`. Every command, SDK event, interrupt and message to Clara is there as JSONL.

Optional, from a third terminal, to show the isolation in detail:

```sh
uv run workflow-agent-runner probe
```

It prints the startup info, including the tools Claude has, and asks Claude to report any CLAUDE.md, memory or skills it can see. It should find none.

## Runner commands

```sh
uv run workflow-agent-runner                  # same as `serve`
uv run workflow-agent-runner serve --port 8787 --origin http://localhost:5173
uv run workflow-agent-runner chat             # chat as Clara in the terminal, one message per line
uv run workflow-agent-runner probe [--text "..."]   # one command, print every event
uv run workflow-agent-runner --claude bundled ...   # force the SDK's bundled Claude Code
uv run workflow-agent-runner --claude <path> ...    # use a specific Claude Code
```

The runner can also run straight from GitHub. You still need the SPA from a clone.

```sh
uvx --from git+https://github.com/gpickell/poc-workflow-agent-runner workflow-agent-runner
```

## Smoke test

With the runner and SPA running:

```sh
uv run python tests/ui_smoke.py            # headless; screenshots go to ./ui-smoke
uv run python tests/ui_smoke.py --headed   # watch it
```

It drives your installed Edge through Playwright, with a throwaway profile. It covers connect, Markdown, Shift+Enter, the working bar, tab replay, Stop, web search, links and New chat. It costs about $0.10 per run.

## Layout

| Path | What |
|------|------|
| `src/workflow_agent_runner/session.py` | Claude Code boot options and the turn loop, including the fallback |
| `src/workflow_agent_runner/tools.py` | `talk_at_clara`, an in-process MCP tool |
| `src/workflow_agent_runner/system_prompt.md` | Clara persona and command format |
| `src/workflow_agent_runner/server.py` | WebSocket server: queue, interrupt, reset, replay, transcripts |
| `src/workflow_agent_runner/protocol.py` | SPA and runner messages (mirrored in `spa/src/protocol.ts`) |
| `src/workflow_agent_runner/cli.py` | Commands and the Claude Code preflight |
| `spa/src/` | React + MUI chat: `useRunner.ts` (connection), `Chat.tsx`, `App.tsx` |
| `tests/ui_smoke.py` | Browser smoke test |

## Troubleshooting

- **"Claude Code is not signed in"** in the chat: run `claude` in a terminal, sign in, then press **New chat**.
- **Chip stuck on "Connecting…" or "Runner offline":** check the runner is running and listening on 8787.
- **SPA won't start on 5173:** something else has the port. The runner only accepts that origin, so free the port rather than moving the SPA (or pass `--origin`).
- **`uv run` fails with "file is being used by another process"** on Windows: a running runner locks its own executable. Stop it first.

## Known limits

- One Claude Code session per runner. Commands run one at a time, in order.
- Restarting the runner starts a new session, so open tabs clear.
- The origin check only stops browser pages; any local program can connect. There is no pairing token in the PoC.
- Before shipping to customers, Anthropic's terms on subscription logins need an answer. See "Terms" in [PLAN.md](PLAN.md).
