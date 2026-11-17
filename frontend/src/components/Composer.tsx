export function Composer({
  draft,
  onDraftChange,
  onSend,
  chatting,
}: {
  draft: string
  onDraftChange: (value: string) => void
  onSend: () => void
  chatting: boolean
}) {
  return (
    <footer className="composer">
      <textarea
        value={draft}
        rows={2}
        placeholder="Ask about hotels, availability, policies or comparisons..."
        onChange={(event) => onDraftChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            onSend()
          }
        }}
        aria-label="Chat message"
      />
      <button type="button" onClick={onSend} disabled={chatting || draft.trim().length === 0}>
        {chatting ? '...' : 'Send'}
      </button>
    </footer>
  )
}
