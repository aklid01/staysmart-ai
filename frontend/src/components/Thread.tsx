import { useEffect, useRef } from 'react'
import type { ApiError } from '../api'
import type { ChatTurn, HotelEntry } from '../types'
import { MessageView } from './MessageView'

export function Thread({
  turns,
  chatting,
  error,
  onDetails,
  onPolicies,
}: {
  turns: ChatTurn[]
  chatting: boolean
  error: ApiError | null
  onDetails: (entry: HotelEntry) => void
  onPolicies: (hotelId: string) => void
}) {
  const threadRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [turns, chatting])

  return (
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
        <MessageView key={index} turn={turn} onDetails={onDetails} onPolicies={onPolicies} />
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
  )
}
