import type { HotelComparison } from '../types'
import { moneyOrText } from '../format'

export function ComparisonTable({ comparison }: { comparison: HotelComparison }) {
  return (
    <div className="comparison-block" data-testid="comparison-table">
      <div className="comparison-context">
        {comparison.check_in} to {comparison.check_out} · {comparison.rooms} room(s),{' '}
        {comparison.guests} guests · {comparison.currency} · mock data
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Hotel</th>
              <th>Nightly</th>
              <th>Total stay</th>
              <th>Rating</th>
              <th>Location</th>
              <th>Cancellation</th>
              <th>Available</th>
            </tr>
          </thead>
          <tbody>
            {comparison.rows.map((row) => (
              <tr key={row.hotel_id}>
                <td>{row.name}</td>
                <td>{moneyOrText(row.nightly_price, comparison.currency, 'not available')}</td>
                <td>{moneyOrText(row.total_stay_price, comparison.currency, 'not available')}</td>
                <td>{row.guest_rating.toFixed(1)}</td>
                <td>{row.location}</td>
                <td>
                  <span className={`policy-badge ${row.cancellation_policy}`}>
                    {row.cancellation_policy.replace('_', ' ')}
                  </span>
                </td>
                <td>{row.availability ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {comparison.unresolved_hotel_ids.length > 0 && (
        <p className="notice">
          Not found in the dataset: {comparison.unresolved_hotel_ids.join(', ')}
        </p>
      )}
      {comparison.unmet_preferences.length > 0 && (
        <p className="notice">Unmet preferences: {comparison.unmet_preferences.join('; ')}</p>
      )}
    </div>
  )
}
