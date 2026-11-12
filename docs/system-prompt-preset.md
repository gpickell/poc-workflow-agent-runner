# Note: using Claude Code's system prompt (preset + append)

Status: likely for production, not done in the PoC. Checked against `claude-agent-sdk` 0.2.180 (Python).

## Why

Workflows are scripts written by technical people, so Claude Code's own system prompt is valuable: it carries the "building things" behavior (planning, working in steps, checking its work, caution with tool output). The PoC passes a custom string as `system_prompt`, which **replaces** that prompt entirely. Claude keeps the harness (agent loop, compaction, resume, caching, tool gating) but loses Claude Code's instructions and the guardrails written into them.

## How

Keep the default prompt and append the app's instructions:

```python
system_prompt={
    "type": "preset",
    "preset": "claude_code",
    "append": CLARA_PROMPT,            # added after Claude Code's own prompt
    "exclude_dynamic_sections": True,  # see below
}
```

- The SDK passes this to the CLI as `--append-system-prompt <text>`.
- TypeScript SDK: the same object, `{ type: "preset", preset: "claude_code", append: "..." }`.

## Gotchas

- **Unset is not the default.** With `system_prompt` unset, the Python SDK passes `--system-prompt ""`, an empty prompt. Ask for the preset explicitly.
- **`exclude_dynamic_sections: True`.** Moves the per-user and per-machine parts (working directory, memory, git status) out of the system prompt and into the first user message. The system prompt is then identical across agent instances, so the prompt cache is shared across customers. Use it when many instances share the preset.
- **`snapshot` (defaults to `True`).** A session keeps the prompt from its first request, including after resume. A release that changes `append` doesn't reach existing sessions until they compact or start fresh. Good for consistency; plan rollouts around it. Set `False` while iterating on the prompt. Needs CLI 2.1.257 or later.
- **Output channel.** Claude Code's prompt assumes the user reads its final text, and it mentions tools we turn off (Bash, file editing). The appended prompt must state the "only talk through `talk_at_clara`" rule firmly. The runner's fallback (show the final text, marked "fallback") still catches misses.

## When adopting

- Switch `Session._options()` in `src/workflow_agent_runner/session.py` to the preset.
- Rework `system_prompt.md` as appended text: drop anything the preset already covers and strengthen the output-channel rule.
- Watch the fallback rate and tokens per turn: the preset adds a large, cached prefix.
