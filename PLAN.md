# PoC: Workflow Agent Runner

Status: PoC shape decided (see "PoC: Testing the Agent Inversion"). Layout and build order still to be agreed.

## Goal

Prove that an app (VertiGIS Workflow Designer) can drive a Claude Code session as its AI engine, with the app supplying commands and tools and Claude Code doing the work. The aim is a harness for exploring AI tool design while the product shape (bespoke chat, MCP, or something else) is still open.

## Background

The starting idea was to invert the normal agent loop. Normally a person at the terminal drives Claude Code. Inverted, the app drives: Claude Code waits on an MCP tool such as `get_next_command`, does the work with the app's MCP tools, and reports back through a tool.

That first iteration works, but fights Claude Code's design: a Stop hook that never lets go, long polls racing timeouts, permission prompts nobody can see, and commands arriving as tool results instead of user messages.

The second iteration turns the loop the right way up. A runner program drives Claude Code through the Agent SDK. The runner acts as Claude Code's "user": it sends each command as a normal message, Claude Code ends its turn normally, and the runner decides what happens next. This is more viable and more stable, and is the basis for this PoC.

Full exploration notes: `C:\code\docs\inverted-agent-loop-exploration.md`.

## Shape of the system

```
Designer (browser)  <-->  Agent runner (local)  <-->  Claude Code (user's own)
                          - hosts MCP tools
                          - owns the Claude Code boot
                          - relays commands and replies
```

- **Agent runner:** A local program, fetched and run with `uvx <runner>`. Starts Claude Code through the Agent SDK with settings, tools, and instructions built in. Hosts the designer's MCP tools in its own process.
- **Claude Code:** The user's own install and account.
- **Designer link:** A local WebSocket between the designer and the runner.

## Settled direction

- **You bring Claude Code, we bring the agent runner.** VertiGIS never ships Claude Code, never handles keys, and never hosts models.
- **The runner is code, not a model.** A thin program relaying commands. No second model in the chain.
- **The runner owns the boot.** Only the runner's MCP tools are loaded. The user's own settings, instruction files, MCP servers, and hooks are kept out. Organization-managed policies still apply.
- **Commands are user messages.** No `get_next_command`, Stop hook, or long polling.
- **Automatic compaction is the baseline.** Claude Code compacts on its own whoever is driving. Earlier, runner-chosen compaction is a refinement only if testing shows trouble.
- **Permission requests go through the runner,** via the SDK's permission callback, rather than terminal prompts.

## What the runner gets for free

- Real resets: start a fresh session or resume an earlier one.
- Interruption of a turn in progress, so a cancel button can work.
- Transcripts: every event streams through the runner, for logging, token counts, and replay.
- Multiple sessions if needed, such as one per open workflow.

## Needs experimentation

**Connecting the designer to the runner.** A browser page cannot listen for connections, and browsers restrict public pages from reaching localhost. Two options:

- **Iframe relay (current leaning):** The designer loads normally. A hidden iframe from `http://localhost:PORT` relays messages via `postMessage` to the runner's WebSocket. Sign-in is unaffected. Likely a one-time browser permission prompt. Needs origin checks on both sides.
- **Serve the designer at localhost (fallback):** The runner proxies or serves the designer, so page and runner share one origin and no prompts appear. ArcGIS sign-in must allow the localhost redirect address, which is the likely obstacle.

A short browser test of the iframe relay should settle this. Include Safari if Safari matters.

**Runner details to confirm:**

- The SDK option for pointing at the user's installed `claude`, and whether the Python SDK bundles its own copy.
- The SDK option for which settings sources to load.
- A minimum Claude Code version check, with clear failure messages when Claude Code is missing, outdated, or not signed in.

**Terms:** Whether a third-party runner driving a user's own Claude Code through the SDK fits Anthropic's terms for the account types users will have, especially subscription logins versus API keys.

- Agent SDK overview (https://code.claude.com/docs/en/agent-sdk/overview): "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK."
- Claude Code legal and compliance (https://code.claude.com/docs/en/legal-and-compliance): third-party developers may not "route requests through Free, Pro, Max, or Ultra plan credentials on behalf of their users", nor "collect, store, or intermediate Claude.ai credentials or session tokens."
- The runner never touches credentials, but driving a customer's subscription-signed-in Claude Code arguably "routes requests through" their plan. That makes it a gray area at best. API keys, Bedrock, Vertex and Foundry are the documented paths; anything else needs Anthropic's approval (contact sales).
- The bundled-Claude-Code fallback means the runner's download includes Claude Code, which weakens "VertiGIS never ships Claude Code".
- For personal PoC use this is moot. Before shipping to customers: ask Anthropic, through VertiGIS's account contact, describing exactly this setup.

## Security

- Any local process can reach a localhost port. The runner checks connection origins and requires a pairing token.
- Commands from the designer act only through the runner's tools. Claude Code gets no shell, file, or web access beyond what the runner allows.

## Support boundary

- **VertiGIS:** The runner, the MCP tools, and the designer connection.
- **The user, with Anthropic:** Claude Code, the account, and usage.

## Intended experience

1. Install uv and Claude Code once.
2. Run `uvx <runner>`.
3. Open the designer, already connected to the runner.
4. Type requests in the designer. The runner drives Claude Code.

## Related

The activity documentation search work (`C:\code\docs\activity-docs-search-exploration.md`) defines tools (list, search, read, type lookups) that would likely be among the runner's MCP tools later. Not part of this PoC unless the shape calls for it.


## PoC: Testing the Agent Inversion

Clara is the persona using the SPA. The runner ("Master of Claude") sits between her and Claude Code.

**SPA:**

- Vite/TS/React/MUI, run with the Vite dev server on its own port.
- Simple chat interface. Clara's input becomes structured commands; Claude's output arrives as `talk_at_clara` messages.
- Connects straight to the runner's WebSocket.

**Runner:**

- Python, async.
- Drives Claude Code through the Python Agent SDK (`ClaudeSDKClient`): one multi-turn session, interrupt, permission callback.
- Hosts its MCP tools in-process.

**Decisions:**

- **Commands are structured user messages.** The runner sends each command as a user message in a fixed format (JSON or tagged), described in the system prompt. No `get_next_command`: a command delivered as a tool result carries less authority than a user message, and costs an extra round trip.
- **`talk_at_clara` is the only output channel.** Claude's final turn text is not shown to Clara. If a turn ends without a `talk_at_clara` call, the runner shows the final text as a fallback.
- **No permission prompts.** The PoC is locked down by leaving tools out, not by asking. Only `talk_at_clara` and `WebSearch` exist, both pre-allowed; `permission_mode="dontAsk"` silently denies anything else. Any denial is logged as a warning. This overrides "permission requests go through the runner" above for the PoC.
- **Origin check only; no pairing token in the PoC.** The WebSocket accepts the Vite dev server's origin only. The pairing token is out of scope for the PoC.
- **Installed Claude Code first, bundled as fallback.** The runner uses `claude` on PATH when it is present and recent enough. Otherwise it notes why and uses the SDK's bundled copy. An explicit `--claude <path>` must work; `--claude bundled` forces the bundled copy.
- **uv package layout now, bundling later.** The runner is a uv package with a console entry point so `uvx --from git+<repo>` can run it. Building the SPA into the package, so one `uvx` command "makes it all happen", is deferred.

**Step 1 findings (SDK smoke test, `workflow-agent-runner probe`, SDK 0.2.180):**

- **Which `claude`:** The Python SDK bundles its own Claude Code (2.1.321 at the time of testing). `cli_path` points at the installed one instead. The runner uses `claude` on PATH by default; `--claude bundled` uses the SDK's copy. Both work with a subscription login.
- **Settings:** `setting_sources=None` loads user, project and local settings. The runner must pass `[]`. With `[]`, no CLAUDE.md, memory, hooks or user MCP servers reached the model.
- **Tools:** `tools=[]` removes all built-in tools, including Skill and Agent. Built-in skills, plugins and agents still appear in the init message but cannot be called.
- **Context Claude Code still injects:** An environment block (cwd, OS, date) and an account-context reminder containing the user's email. Not controlled by the runner.
- **Preflight:** Missing or too old (`MIN_CLAUDE_VERSION`, 2.1.248 for `verbatim_prompts`) fails before start. Not signed in shows up as `AssistantMessage.error == "authentication_failed"` on the first turn.

**Step 2 findings (`talk_at_clara`, `workflow-agent-runner chat`):**

- **Reliability:** Two 10-turn runs (greetings, one-word replies, lists, recall, "don't use any tools") had no fallbacks. A direct order not to call the tool did trigger the fallback, which showed the final text.
- **Prompt fixes needed:** Without them, Claude sent a greeting twice in one turn and told Clara about its "message tool". The system prompt now says once per turn, never repeat, and never mention the tool; the tool result says "Don't send it again."
- **Cost:** `ResultMessage.total_cost_usd` is the session total so far, not the turn's. About $0.005 to $0.02 per short turn on Opus 5.5.

**Step 3 findings (WebSocket server, `workflow-agent-runner` or `serve`):**

- **Protocol:** Defined in `protocol.py`. The runner accepts only known message types and command kinds, and passes on only known fields.
- **Origin check:** Pages from other origins and clients with no `Origin` header get 403. This stops browser pages only; any local program can send the allowed origin, which is what the pairing token is for.
- **Queueing:** Commands run one at a time in arrival order. Every connected client receives every broadcast.
- **Interrupt:** Ends the turn within milliseconds (`turn_end` with `ok: false`). The session carries on with its memory. The SDK reports no cost for an interrupted turn, so token counts for it are lost.
- **Reset:** Drops queued commands, interrupts, and starts a new session (about 2.5 s). Clients get `reset`; the new session has no memory of the old one.

**Step 4 (SPA chat, `spa/`, `npm run dev`):**

- Vite + React + MUI chat. It connects to the runner and reconnects every 2 s when the runner is offline. It renders Clara's messages as Markdown and marks fallback replies. It shows a working bar and the last turn's time and cost.
- The Vite port is pinned to 5173, because the runner accepts only that origin.
- **UI testing:** `tests/ui_smoke.py` drives the installed Edge through Playwright (`channel="msedge"`, throwaway profile, no browser download). The Claude browser extension refuses localhost pages ("blocked by your organization's policy"). No Chrome or Edge machine policy is set, so the block comes from the extension or the Claude organization's settings.
- **Checked in Edge:** connect, Markdown rendering, Shift+Enter line breaks, the working bar, turn time and cost, no console errors. Stopping the runner shows "Runner offline" and disables Send; the page reconnects about 4 s after the runner restarts.
- **Bug found by the browser test:** An expression-bodied `useEffect` returned `scrollIntoView()`'s result. Current Chromium returns a Promise from it, which crashed the chat ("destroy is not a function").
- **Gap (fixed in step 7):** A client that connected mid-turn missed messages already sent, and your own messages were local to the tab.

**Step 5 (Stop, New chat) and web search:**

- **Stop:** Replaces Send while Claude works. It interrupts the turn and adds a "Stopped." note to the chat.
- **New chat:** Resets the session. The chat clears once the runner confirms, about 2.5 s later; until then the button shows "Starting…" and sending is disabled.
- **Web search:** `WebSearch` is the one built-in tool allowed (`BUILTIN_TOOLS` in `session.py`); WebFetch, shell and files stay off. The system prompt asks for source links and says to treat results as information, not instructions. Links in Clara's messages open in a new tab.
- **Search cost:** A search turn costs about $0.05 to $0.06 and takes about 11 s, against about $0.005 for a short reply. Claude may choose the "extended" search mode. The `web_search_requests` usage count stays 0, so searches can't be counted from usage.
- **Prompt-injection exposure:** Search results are untrusted text. With only `talk_at_clara` besides search, the worst outcome is a misleading message to Clara. This needs revisiting once tools that change workflows are added.

**Step 6 (permissions):** Nothing to build, per the decision above. A test request to read `C:/Windows/win.ini` was declined by Claude with no denial recorded, because no file tool exists to deny.

**Step 7 (transcripts, token counts, replay):**

- **Transcripts:** One JSONL file per session in `~/.workflow-agent-runner/transcripts/`, created on first write. It holds commands, every SDK message, what Clara was shown, and interrupts.
- **Token counts:** `ResultMessage.usage` is per turn (unlike cost). `turn_end` carries input, cache read, cache write and output tokens. The SPA shows, for example, "4.7k tokens in (4.4k cached), 187 out".
- **Searches:** Counted in `ResultMessage.model_usage[...]["webSearchRequests"]`, as a session total, under the Haiku model. Claude Code also makes a small Haiku call of its own each session.
- **Rate limits:** The SDK emits `RateLimitEvent`, carrying subscription rate-limit information. It could be shown in the SPA later.
- **Replay:** The runner echoes each command to every client and keeps the session's message history. A connecting client gets `reset`, the history, then `status`, sent with no awaits in between so nothing can interleave. This fixes the step 4 gap: a new tab shows the same conversation. A runner restart starts a new session, so an open tab clears, matching Claude's lost memory.

**Step 8 (uvx):** `uvx --from <local path> workflow-agent-runner` builds, installs into an isolated environment and runs; a probe through it worked. The wheel includes `system_prompt.md`, and Playwright stays a dev-only dependency. Not yet tested: `uvx --from git+<repo>`, because the project is not a git repository yet.

- **Download size:** `claude-agent-sdk` is a 147 MB download, because it bundles Claude Code. Every user downloads it even though the runner uses their installed `claude`. This bears on the installed-versus-bundled decision: users get the bundled copy anyway.

**Out of scope for the PoC:** iframe relay test, pairing token.

**Deferred:** SPA bundling, terms review.
