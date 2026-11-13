import { useEffect, useRef, useState } from 'react'
import { ApiError, getHealth, postChat } from './api'
import type { ChatTurn, HealthResponse, HotelEntry } from './types'
import { HotelCard } from './components/HotelCard'
import { ComparisonTable } from './components/ComparisonTable'
import { SourceChips, ToolTraceChips } from './components/Chips'
import { DetailsDialog, PolicyDialog } from './components/Dialogs'
import { MarkdownLite } from './components/MarkdownLite'

const HISTORY_LIMIT = 10

function newConversationId(): string {
  const bytes = new Uint8Array(6)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

function MessageView({
  turn,
  onDetails,
  onPolicies,
}: {
  turn: ChatTurn
  onDetails: (entry: HotelEntry) => void
  onPolicies: (hotelId: string) => void
}) {
  if (turn.role === 'user') {
    return (
      <div
        className={
          turn.status === 'failed' ? 'bubble user-bubble user-bubble-failed' : 'bubble user-bubble'
        }
      >
        {turn.content}
      </div>
    )
  }
  const response = turn.response
  return (
    <div className="assistant-block">
      <div className="bubble assistant-bubble">
        <MarkdownLite text={turn.content} />
      </div>
      {response && response.outcome === 'budget_exhausted' && (
        <p className="notice">
          The answer was summarized early: the tool budget for this turn ran out.
        </p>
      )}
      {response && response.outcome === 'turns_exhausted' && (
        <p className="notice">
          The answer was summarized early: the turn limit was reached before a final answer.
        </p>
      )}
      {response && response.hotels.length > 0 && (
        <div className="card-grid">
          {response.hotels.map((entry) => (
            <HotelCard
              key={entry.hotel.hotel_id}
              entry={entry}
              onDetails={onDetails}
              onPolicies={onPolicies}
            />
          ))}
        </div>
      )}
      {response?.comparison && <ComparisonTable comparison={response.comparison} />}
      {response && <SourceChips sources={response.sources} />}
      {response && <ToolTraceChips trace={response.tool_trace} />}
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [draft, setDraft] = useState('')
  const [chatting, setChatting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [dialog, setDialog] = useState<
    { kind: 'details'; entry: HotelEntry } | { kind: 'policy'; hotelId: string } | null
  >(null)
  const conversationIdRef = useRef(newConversationId())
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [turns, chatting])

  async function sendMessage() {
    const message = draft.trim()
    if (!message || chatting) return
    setDraft('')
    setError(null)
    const history = turns
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
      const apiError = exc instanceof ApiError ? exc : new ApiError('unknown_error', String(exc), 0)
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

  const healthLabel = health
    ? health.status === 'ok'
      ? 'API connected'
      : 'API degraded'
    : 'API offline'

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">🏨</span>
          <div>
            <h1>StaySmart AI</h1>
            <p className="brand-sub">Hotel discovery assistant</p>
          </div>
        </div>
        <div className="header-status">
          <span
            className={`health-dot ${health ? (health.status === 'ok' ? 'ok' : 'degraded') : 'offline'}`}
          />
          <span className="health-label">{healthLabel}</span>
          <span
            className="mock-badge"
            title="All provider data in this MVP is mock data (data_source=mock, is_live=false)"
          >
            mock data
          </span>
        </div>
      </header>

      <main className="thread" ref={threadRef}>
        {turns.length === 0 && !chatting && (
          <div className="empty-state">
            <h2>Where would you like to stay?</h2>
            <p>
              Ask in plain language, for example:{' '}
              <em>
                Find a hotel in Kyoto for two guests in December under 250 with breakfast and wifi.
              </em>
            </p>
            <p className="muted-row">
              The assistant searches live mock hotel data and can answer policy questions with cited
              sources.
            </p>
          </div>
        )}
        {turns.map((turn, index) => (
          <MessageView
            key={index}
            turn={turn}
            onDetails={(entry) => setDialog({ kind: 'details', entry })}
            onPolicies={(hotelId) => setDialog({ kind: 'policy', hotelId })}
          />
        ))}
        {chatting && (
          <div className="typing-row" aria-label="Assistant is thinking">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-label">Thinking...</span>
          </div>
        )}
        {error && (
          <div className="error-banner" role="alert">
            <strong>[{error.code}]</strong> {error.message}
          </div>
        )}
      </main>

      <footer className="composer">
        <textarea
          value={draft}
          rows={2}
          placeholder="Ask about hotels, availability, policies or comparisons..."
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              sendMessage()
            }
          }}
          aria-label="Chat message"
        />
        <button
          type="button"
          onClick={sendMessage}
          disabled={chatting || draft.trim().length === 0}
        >
          {chatting ? '...' : 'Send'}
        </button>
      </footer>

      {dialog?.kind === 'details' && (
        <DetailsDialog
          key={dialog.entry.hotel.hotel_id}
          entry={dialog.entry}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === 'policy' && (
        <PolicyDialog
          key={dialog.hotelId}
          hotelId={dialog.hotelId}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  )
}
