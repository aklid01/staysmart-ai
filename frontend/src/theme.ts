import type { Hotel } from './types'

export interface DestinationTheme {
  match: string
  gradient: string
  label: string
}

export const DESTINATION_THEMES: DestinationTheme[] = [
  {
    match: 'lisbon',
    gradient: 'linear-gradient(135deg, #0f766e 0%, #f59e0b 100%)',
    label: 'Lisbon',
  },
  { match: 'kyoto', gradient: 'linear-gradient(135deg, #b91c1c 0%, #f472b6 100%)', label: 'Kyoto' },
  {
    match: 'vancouver',
    gradient: 'linear-gradient(135deg, #1d4ed8 0%, #10b981 100%)',
    label: 'Vancouver',
  },
]

export const NEUTRAL_GRADIENT = 'linear-gradient(135deg, #334155 0%, #64748b 100%)'

export function themeFor(hotel: Hotel): DestinationTheme | null {
  return DESTINATION_THEMES.find((theme) => hotel.destination_id.includes(theme.match)) ?? null
}
