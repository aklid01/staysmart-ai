import { useEffect, useState } from 'react'
import { getHealth } from './api'
import type { HealthResponse } from './types'
import { ActiveDialog, type DialogState } from './components/ActiveDialog'
import { AppHeader } from './components/AppHeader'
import { Composer } from './components/Composer'
import { Thread } from './components/Thread'
import { useChat } from './hooks/useChat'

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [draft, setDraft] = useState('')
  const [dialog, setDialog] = useState<DialogState>(null)
  const { turns, chatting, error, sendMessage } = useChat()

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  async function handleSend() {
    const message = draft.trim()
    if (!message || chatting) return
    setDraft('')
    await sendMessage(message)
  }

  return (
    <div className="app-shell">
      <AppHeader health={health} />
      <Thread
        turns={turns}
        chatting={chatting}
        error={error}
        onDetails={(entry) => setDialog({ kind: 'details', entry })}
        onPolicies={(hotelId) => setDialog({ kind: 'policy', hotelId })}
      />
      <Composer draft={draft} onDraftChange={setDraft} onSend={handleSend} chatting={chatting} />
      <ActiveDialog dialog={dialog} onClose={() => setDialog(null)} />
    </div>
  )
}
