import { useCallback, useEffect, useRef, useState } from 'react'
import type { FromRunner, ToRunner, Tokens } from './protocol'

const RUNNER_URL = import.meta.env.VITE_RUNNER_URL ?? 'ws://127.0.0.1:8787'
const RETRY_MS = 2000

export type Connection = 'connecting' | 'open' | 'closed'

export type ChatMessage =
  | { key: string; from: 'you'; text: string }
  | { key: string; from: 'clara'; text: string; fallback: boolean }
  | { key: string; from: 'error'; text: string }
  | { key: string; from: 'note'; text: string }

type NewMessage = ChatMessage extends infer M ? (M extends ChatMessage ? Omit<M, 'key'> : never) : never

export type TurnInfo = { ok: boolean; durationMs: number; costUsd: number; tokens: Tokens }

export function useRunner() {
  const [connection, setConnection] = useState<Connection>('connecting')
  const [working, setWorking] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [lastTurn, setLastTurn] = useState<TurnInfo>()
  const [resetting, setResetting] = useState(false)
  const socket = useRef<WebSocket>(null)

  const add = (message: NewMessage) =>
    setMessages(list => [...list, { ...message, key: crypto.randomUUID() } as ChatMessage])

  useEffect(() => {
    let stopped = false
    let retry: ReturnType<typeof setTimeout>

    function open() {
      setConnection('connecting')
      const ws = new WebSocket(RUNNER_URL)
      socket.current = ws
      ws.onopen = () => setConnection('open')
      ws.onclose = () => {
        setConnection('closed')
        setWorking(false)
        setResetting(false)
        if (!stopped) retry = setTimeout(open, RETRY_MS)
      }
      ws.onmessage = event => receive(JSON.parse(event.data) as FromRunner)
    }

    function receive(message: FromRunner) {
      switch (message.type) {
        case 'status':
          setWorking(message.state === 'working')
          break
        case 'command':
          add({ from: 'you', text: message.command.text })
          break
        case 'clara':
          add({ from: 'clara', text: message.text, fallback: message.fallback })
          break
        case 'turn_end':
          setLastTurn({ ok: message.ok, durationMs: message.durationMs, costUsd: message.costUsd, tokens: message.tokens })
          if (!message.ok) add({ from: 'note', text: 'Stopped.' })
          break
        case 'error':
          add({ from: 'error', text: message.message })
          break
        case 'reset':
          setMessages([])
          setLastTurn(undefined)
          setResetting(false)
          break
      }
    }

    open()
    return () => {
      stopped = true
      clearTimeout(retry)
      socket.current?.close()
    }
  }, [])

  const post = useCallback((message: ToRunner) => socket.current?.send(JSON.stringify(message)), [])

  const send = useCallback(
    // The runner echoes the command to every client; that echo adds it to the chat.
    (text: string) => {
      post({ type: 'command', id: crypto.randomUUID(), command: { kind: 'chat', text } })
    },
    [post],
  )

  const interrupt = useCallback(() => post({ type: 'interrupt' }), [post])

  const reset = useCallback(() => {
    setResetting(true)
    post({ type: 'reset' })
  }, [post])

  return { connection, working, resetting, messages, lastTurn, send, interrupt, reset }
}
