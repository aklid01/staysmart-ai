import { useRef, useState } from 'react'
import { ApiError, postChat } from '../api'
import type { ChatTurn, HistoryEntry } from '../types'

const HISTORY_LIMIT = 10

function newConversationId(): string {
  const bytes = new Uint8Array(6)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function useChat() {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [chatting, setChatting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const conversationIdRef = useRef(newConversationId())

  async function sendMessage(message: string) {
    if (!message || chatting) return
    setError(null)
    const history: HistoryEntry[] = turns
      .filter((turn) => turn.status !== 'failed')
      .slice(-HISTORY_LIMIT)
      .map((turn) => ({ role: turn.role, content: turn.content }))
    setTurns((current) => [...current, { role: 'user', content: message }])
    setChatting(true)
    try {
      const response = await postChat({
        message,
        conversation_id: conversationIdRef.current,
        history,
      })
      setTurns((current) => [
        ...current,
        { role: 'assistant', content: response.message, response },
      ])
    } catch (exc) {
      const apiError = exc instanceof ApiError ? exc : new ApiError('unknown_error', String(exc))
      setError(apiError)
      setTurns((current) => {
        const next = [...current]
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === 'user' && next[i].status !== 'failed') {
            next[i] = { ...next[i], status: 'failed' }
            break
          }
        }
        return next
      })
    } finally {
      setChatting(false)
    }
  }

  return { turns, chatting, error, sendMessage }
}
