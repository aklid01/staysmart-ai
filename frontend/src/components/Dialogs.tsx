import { useEffect, useMemo, useState } from 'react'
import { ApiError, getHotelDetails, getHotelPolicies } from '../api'
import type { HotelDetailsPayload, HotelEntry, PolicyInfo } from '../types'
import { isSearchHit } from '../types'

function DialogShell({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="dialog-overlay" onClick={onClose} role="presentation">
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="dialog-head">
          <h2>{title}</h2>
          <button type="button" className="dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="dialog-body">{children}</div>
      </div>
    </div>
  )
}

function roomOf(entry: HotelEntry, roomTypeId: string) {
  return entry.hotel.room_types.find((roomType) => roomType.room_type_id === roomTypeId)
}

function roomName(entry: HotelEntry, roomTypeId: string): string {
  return roomOf(entry, roomTypeId)?.name ?? roomTypeId
}

export function DetailsDialog({ entry, onClose }: { entry: HotelEntry; onClose: () => void }) {
  const hotel = entry.hotel
  const stay = useMemo(
    () =>
      isSearchHit(entry)
        ? { check_in: entry.quote.check_in, check_out: entry.quote.check_out }
        : undefined,
    [entry],
  )
  const [details, setDetails] = useState<HotelDetailsPayload | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    getHotelDetails(hotel.hotel_id, stay)
      .then((payload) => {
        if (!cancelled) setDetails(payload)
      })
      .catch((exc: ApiError) => {
        if (!cancelled) setError(exc)
      })
    return () => {
      cancelled = true
    }
  }, [hotel.hotel_id, stay])

  return (
    <DialogShell title={`${hotel.name} - details`} onClose={onClose}>
      {error && (
        <p className="error-banner">
          [{error.code}] {error.message}
        </p>
      )}
      {!error && !details && <p className="loading-row">Loading details...</p>}
      {details && (
        <>
          <p className="muted-row">
            {details.check_in} to {details.check_out} · {details.rooms} room(s), {details.guests}{' '}
            guests · {details.currency} · mock data
          </p>
          <p>{details.hotel.description}</p>
          <table className="details-table">
            <thead>
              <tr>
                <th>Room</th>
                <th>Beds</th>
                <th>Sleeps</th>
                <th>Nights</th>
                <th>Avg / night</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {details.room_quotes.map((quote) => {
                const room = roomOf(entry, quote.room_type_id)
                return (
                  <tr key={quote.room_type_id}>
                    <td>{roomName(entry, quote.room_type_id)}</td>
                    <td>{room?.bed_type ?? '-'}</td>
                    <td>{room?.max_occupancy ?? '-'}</td>
                    <td>
                      {quote.nights_available}/{quote.nights}
                    </td>
                    <td>
                      {quote.avg_nightly_rate == null ? '-' : quote.avg_nightly_rate.toFixed(2)}
                    </td>
                    <td>{quote.total_price == null ? '-' : quote.total_price.toFixed(2)}</td>
                    <td>
                      {quote.available
                        ? 'Available'
                        : `Sold out${quote.sold_out_dates.length > 0 ? `: ${quote.sold_out_dates.join(', ')}` : ''}`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <h3>Cancellation</h3>
          <p>
            {details.cancellation_policy.description}{' '}
            <span className={`policy-badge ${details.cancellation_policy.policy_type}`}>
              {details.cancellation_policy.policy_type.replace('_', ' ')}
            </span>
          </p>
        </>
      )}
    </DialogShell>
  )
}

export function PolicyDialog({ hotelId, onClose }: { hotelId: string; onClose: () => void }) {
  const [policy, setPolicy] = useState<PolicyInfo | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    getHotelPolicies(hotelId)
      .then((payload) => {
        if (!cancelled) setPolicy(payload)
      })
      .catch((exc: ApiError) => {
        if (!cancelled) setError(exc)
      })
    return () => {
      cancelled = true
    }
  }, [hotelId])

  return (
    <DialogShell title={`Policies - ${policy?.hotel_name ?? hotelId}`} onClose={onClose}>
      {error && (
        <p className="error-banner">
          [{error.code}] {error.message}
        </p>
      )}
      {!error && !policy && <p className="loading-row">Loading policies...</p>}
      {policy && (
        <>
          <p>{policy.general_info}</p>
          <h3>Cancellation</h3>
          <p>
            {policy.cancellation_policy.description}{' '}
            <span className={`policy-badge ${policy.cancellation_policy.policy_type}`}>
              {policy.cancellation_policy.policy_type.replace('_', ' ')}
            </span>
          </p>
          <h3>Pets</h3>
          <p>
            {policy.pet_policy}
            <span className="muted-row"> (source: {policy.pet_policy_source})</span>
          </p>
          <h3>Check-in / check-out</h3>
          <p>
            {policy.check_in_time ?? 'not documented'} / {policy.check_out_time ?? 'not documented'}
          </p>
          {policy.information_gaps.length > 0 && (
            <>
              <h3>Information gaps</h3>
              <ul className="gap-row">
                {policy.information_gaps.map((gap) => (
                  <li key={gap} className="gap-chip">
                    {gap.replace(/_/g, ' ')}: not provided by the provider
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </DialogShell>
  )
}
