import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { Alert, Box, Chip, IconButton, LinearProgress, Paper, Stack, TextField, Tooltip, Typography } from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import StopIcon from '@mui/icons-material/Stop'
import type { ChatMessage, TurnInfo } from './useRunner'

function Bubble({ message }: { message: ChatMessage }) {
  if (message.from === 'error') {
    return <Alert severity="error">{message.text}</Alert>
  }
  if (message.from === 'note') {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
        {message.text}
      </Typography>
    )
  }
  const mine = message.from === 'you'
  return (
    <Stack direction="row" sx={{ justifyContent: mine ? 'flex-end' : 'flex-start' }}>
      <Paper
        variant={mine ? 'elevation' : 'outlined'}
        elevation={0}
        sx={{
          px: 2,
          maxWidth: '80%',
          bgcolor: mine ? 'primary.main' : 'background.paper',
          color: mine ? 'primary.contrastText' : 'text.primary',
          '& p': { my: 1.25 },
        }}
      >
        {mine ? (
          <Typography sx={{ py: 1.25, whiteSpace: 'pre-wrap' }}>{message.text}</Typography>
        ) : (
          <Markdown components={{ a: props => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>{message.text}</Markdown>
        )}
        {message.from === 'clara' && message.fallback && (
          <Tooltip title="Claude ended its turn without talk_at_clara; this is its final text.">
            <Chip label="fallback" size="small" color="warning" sx={{ mb: 1 }} />
          </Tooltip>
        )}
      </Paper>
    </Stack>
  )
}

function kilo(n: number) {
  return n < 1000 ? `${n}` : `${(n / 1000).toFixed(1)}k`
}

function describeTurn({ durationMs, costUsd, tokens }: TurnInfo) {
  const input = tokens.input + tokens.cacheRead + tokens.cacheWrite
  return (
    `${(durationMs / 1000).toFixed(1)} s, $${costUsd.toFixed(4)}, ` +
    `${kilo(input)} tokens in (${kilo(tokens.cacheRead)} cached), ${kilo(tokens.output)} out`
  )
}

type Props = {
  messages: ChatMessage[]
  working: boolean
  canSend: boolean
  lastTurn?: TurnInfo
  onSend: (text: string) => void
  onCancel: () => void
}

export default function Chat({ messages, working, canSend, lastTurn, onSend, onCancel }: Props) {
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  // Braces matter: scrollIntoView returns a Promise in current Chromium, and an
  // effect must not return anything but a cleanup function.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = () => {
    const text = draft.trim()
    if (!text || !canSend) return
    onSend(text)
    setDraft('')
  }

  return (
    <Stack sx={{ flex: 1, minHeight: 0 }}>
      <Stack spacing={1.5} sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
        {messages.length === 0 && (
          <Typography color="text.secondary" sx={{ textAlign: 'center', mt: 4 }}>
            Ask for help designing a workflow.
          </Typography>
        )}
        {messages.map(message => (
          <Bubble key={message.key} message={message} />
        ))}
        <div ref={end} />
      </Stack>
      <Box sx={{ height: 4 }}>{working && <LinearProgress />}</Box>
      <Stack direction="row" spacing={1} sx={{ p: 2, pt: 1, alignItems: 'flex-end' }}>
        <TextField
          fullWidth
          multiline
          maxRows={6}
          placeholder="Message (Enter to send, Shift+Enter for a new line)"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
        />
        {working ? (
          <Tooltip title="Stop">
            <IconButton color="error" onClick={onCancel} aria-label="Stop">
              <StopIcon />
            </IconButton>
          </Tooltip>
        ) : (
          <IconButton color="primary" onClick={submit} disabled={!canSend || !draft.trim()} aria-label="Send">
            <SendIcon />
          </IconButton>
        )}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ px: 2, pb: 1, minHeight: 28 }}>
        {lastTurn && `Last turn: ${lastTurn.ok ? '' : 'stopped, '}${describeTurn(lastTurn)}`}
      </Typography>
    </Stack>
  )
}
