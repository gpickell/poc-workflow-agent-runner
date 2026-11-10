import { AppBar, Button, Chip, Stack, Toolbar, Typography } from '@mui/material'
import AddCommentIcon from '@mui/icons-material/AddComment'
import Chat from './Chat'
import { useRunner, type Connection } from './useRunner'

const connectionChip: Record<Connection, { label: string; color: 'success' | 'warning' | 'error' }> = {
  open: { label: 'Runner connected', color: 'success' },
  connecting: { label: 'Connecting…', color: 'warning' },
  closed: { label: 'Runner offline', color: 'error' },
}

export default function App() {
  const { connection, working, resetting, messages, lastTurn, send, interrupt, reset } = useRunner()
  const chip = connectionChip[connection]
  const open = connection === 'open'

  return (
    <Stack sx={{ height: '100vh' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" sx={{ flex: 1 }}>
            Workflow Designer AI
          </Typography>
          <Button color="inherit" startIcon={<AddCommentIcon />} onClick={reset} disabled={!open || resetting}>
            {resetting ? 'Starting…' : 'New chat'}
          </Button>
          <Chip label={chip.label} color={chip.color} size="small" />
        </Toolbar>
      </AppBar>
      <Chat
        messages={messages}
        working={working}
        canSend={open && !resetting}
        lastTurn={lastTurn}
        onSend={send}
        onCancel={interrupt}
      />
    </Stack>
  )
}
