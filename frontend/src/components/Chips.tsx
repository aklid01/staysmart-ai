import type { ContextSource, ToolTraceEntry } from '../types'

export function SourceChips({ sources }: { sources: ContextSource[] }) {
  if (sources.length === 0) return null
  return (
    <div className="source-row" aria-label="knowledge sources">
      <span className="source-label">Sources:</span>
      {sources.map((source) => (
        <span
          key={source.doc_id}
          className="source-chip"
          title={`${source.category} · ${source.chunk_count} chunk(s) · ${source.doc_id}`}
        >
          [{source.title}]
        </span>
      ))}
    </div>
  )
}

export function ToolTraceChips({ trace }: { trace: ToolTraceEntry[] }) {
  if (trace.length === 0) return null
  return (
    <div className="tool-trace">
      {trace.map((entry, index) => (
        <span
          key={index}
          className={`tool-chip status-${entry.status}`}
          title={`status: ${entry.status}`}
        >
          {entry.tool}
        </span>
      ))}
    </div>
  )
}
