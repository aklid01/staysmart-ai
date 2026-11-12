import type { Hotel, HotelEntry } from '../types'
import { isSearchHit } from '../types'
import { amenityLabel } from '../amenities'

const DESTINATION_THEMES: { match: string; gradient: string; label: string }[] = [
  { match: 'lis', gradient: 'linear-gradient(135deg, #0f766e 0%, #f59e0b 100%)', label: 'Lisbon' },
  { match: 'kyo', gradient: 'linear-gradient(135deg, #b91c1c 0%, #f472b6 100%)', label: 'Kyoto' },
  { match: 'van', gradient: 'linear-gradient(135deg, #1d4ed8 0%, #10b981 100%)', label: 'Vancouver' },
]

function themeFor(hotel: Hotel) {
  return DESTINATION_THEMES.find((theme) => hotel.hotel_id.includes(theme.match)) ?? DESTINATION_THEMES[0]
}

interface CardProps {
  entry: HotelEntry
  onDetails: (entry: HotelEntry) => void
  onPolicies: (hotelId: string) => void
}

export function HotelCard({ entry, onDetails, onPolicies }: CardProps) {
  const hotel = entry.hotel
  const theme = themeFor(hotel)
  const quote = isSearchHit(entry) ? entry.quote : null
  const amenities = hotel.amenities.slice(0, 4)
  const extraAmenities = hotel.amenities.length - amenities.length
  const money = (value: number | null | undefined) =>
    value == null ? null : `${value.toFixed(2)} ${hotel.currency}`

  return (
    <article className="hotel-card" data-hotel-id={hotel.hotel_id}>
      <div className="card-image" style={{ background: theme.gradient }}>
        <span className="card-initial">{hotel.name.charAt(0)}</span>
        <span className="card-destination">{theme.label}</span>
        <span className="card-mock" title={`data_source=${hotel.data_source}, is_live=${String(hotel.is_live)}`}>
          mock data
        </span>
      </div>
      <div className="card-body">
        <header className="card-head">
          <h3>{hotel.name}</h3>
          <div className="card-ratings">
            <span className="stars" title={`${hotel.star_rating}-star property`}>{'★'.repeat(hotel.star_rating)}</span>
            <span className="guest-rating" title={`${hotel.review_count} reviews`}>
              {hotel.guest_rating.toFixed(1)}
            </span>
          </div>
        </header>
        <p className="card-location">{hotel.location}</p>
        <p className="card-description">{hotel.description}</p>
        <ul className="amenity-row">
          {amenities.map((amenity) => (
            <li key={amenity} className="amenity-chip">
              {amenityLabel(amenity)}
            </li>
          ))}
          {extraAmenities > 0 && <li className="amenity-chip amenity-more">+{extraAmenities}</li>}
        </ul>
        {quote ? (
          <div className="price-block" data-available={String(quote.available)}>
            {quote.available ? (
              <>
                <span className="price-line">
                  <strong>{money(quote.avg_nightly_rate)}</strong> avg / night
                </span>
                {quote.total_price != null && (
                  <span className="price-line muted">
                    {money(quote.total_price)} total · {quote.nights} nights
                  </span>
                )}
              </>
            ) : (
              <span className="price-line unavailable">
                Sold out for these dates{quote.sold_out_dates.length > 0 ? ` (${quote.sold_out_dates.join(', ')})` : ''}
              </span>
            )}
          </div>
        ) : (
          <div className="price-block">
            <span className="price-line muted">
              {hotel.room_types.length} room type{hotel.room_types.length === 1 ? '' : 's'} · from{' '}
              {money(Math.min(...hotel.room_types.map((room) => room.base_nightly_rate)))} base rate
            </span>
          </div>
        )}
        <footer className="card-actions">
          <span className={`policy-badge ${hotel.cancellation_policy.policy_type}`}>
            {hotel.cancellation_policy.policy_type.replace('_', ' ')}
            {hotel.cancellation_policy.refundable ? ' · refundable' : ' · non-refundable'}
          </span>
          <div className="card-buttons">
            <button type="button" onClick={() => onDetails(entry)}>
              Details
            </button>
            <button type="button" onClick={() => onPolicies(hotel.hotel_id)}>
              Policies
            </button>
          </div>
        </footer>
      </div>
    </article>
  )
}
