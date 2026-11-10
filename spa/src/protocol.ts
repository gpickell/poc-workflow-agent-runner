// Messages between the SPA and the runner. Mirrors src/workflow_agent_runner/protocol.py.

export type Command = { kind: 'chat'; text: string }

export type ToRunner =
  | { type: 'command'; id: string; command: Command }
  | { type: 'interrupt' }
  | { type: 'reset' }

export type Tokens = { input: number; cacheRead: number; cacheWrite: number; output: number }

// On connect the runner sends 'reset', replays the session's history, then sends 'status'.
export type FromRunner =
  | { type: 'status'; state: 'idle' | 'working' }
  | { type: 'command'; id: string; command: Command }
  | { type: 'clara'; text: string; fallback: boolean }
  | { type: 'turn_end'; id: string; ok: boolean; durationMs: number; costUsd: number; tokens: Tokens }
  | { type: 'error'; message: string; id?: string }
  | { type: 'reset' }
