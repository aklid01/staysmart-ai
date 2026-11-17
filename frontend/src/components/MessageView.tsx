import type { ChatTurn, HotelEntry } from '../types'
import { HotelCard } from './HotelCard'
import { ComparisonTable } from './ComparisonTable'
import { SourceChips, ToolTraceChips } from './Chips'
import { MarkdownLite } from './MarkdownLite'

export function MessageView({
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
