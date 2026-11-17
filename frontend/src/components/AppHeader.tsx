import type { HealthResponse } from '../types'

export function AppHeader({ health }: { health: HealthResponse | null }) {
  const healthLabel = health
    ? health.status === 'ok'
      ? 'API connected'
      : 'API degraded'
    : 'API offline'

  return (
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
  )
}
