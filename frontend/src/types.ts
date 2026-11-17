export type PolicyType = 'free' | 'flexible' | 'partial' | 'non_refundable'

export interface CancellationPolicy {
  policy_type: PolicyType
  refundable: boolean
  free_cancellation_days: number
  penalty_nights: number
  description: string
}

export interface RoomType {
  room_type_id: string
  name: string
  max_occupancy: number
  bed_type: string
  base_nightly_rate: number
  total_rooms: number
  amenities: string[]
}

export interface Hotel {
  hotel_id: string
  name: string
  destination_id: string
  location: string
  star_rating: number
  guest_rating: number
  review_count: number
  amenities: string[]
  room_types: RoomType[]
  cancellation_policy: CancellationPolicy
  description: string
  currency: string
  data_source: string
  is_live: boolean
}

export interface StayQuote {
  room_type_id: string
  check_in: string
  check_out: string
  nights: number
  nightly_rates: number[]
  avg_nightly_rate: number | null
  total_price: number | null
  currency: string
  guests: number
  rooms: number
  available: boolean
  partially_available: boolean
  nights_available: number
  sold_out_dates: string[]
  data_source: string
  is_live: boolean
}

export interface SearchHit {
  hotel: Hotel
  quote: StayQuote
  matched_amenities: string[]
}

export interface HotelDetailsPayload {
  hotel: Hotel
  check_in: string
  check_out: string
  rooms: number
  guests: number
  room_quotes: StayQuote[]
  cancellation_policy: CancellationPolicy
  currency: string
  data_source: string
  is_live: boolean
}

export type HotelEntry = SearchHit | HotelDetailsPayload

export function isSearchHit(entry: HotelEntry): entry is SearchHit {
  return 'quote' in entry
}

export interface ComparisonRow {
  hotel_id: string
  name: string
  nightly_price: number | null
  total_stay_price: number | null
  guest_rating: number
  location: string
  amenities: string[]
  cancellation_policy: string
  refundable: boolean
  availability: boolean
}

export interface HotelComparison {
  rows: ComparisonRow[]
  unresolved_hotel_ids: string[]
  check_in: string
  check_out: string
  rooms: number
  guests: number
  currency: string
  unmet_preferences: string[]
}

export interface ContextSource {
  doc_id: string
  title: string
  category: string
  chunk_count: number
  hotel_id: string | null
  destination_id: string | null
}

export type ToolStatus = 'ok' | 'error' | 'duplicate'

export interface ToolTraceEntry {
  tool: string
  status: ToolStatus
}

export type TurnOutcome = 'answered' | 'budget_exhausted' | 'turns_exhausted'

export interface ChatResponse {
  message: string
  hotels: HotelEntry[]
  comparison: HotelComparison | null
  sources: ContextSource[]
  tool_trace: ToolTraceEntry[]
  conversation_id: string
  outcome: TurnOutcome
}

export type TurnStatus = 'sent' | 'failed'

export interface HistoryEntry {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  response?: ChatResponse
  status?: TurnStatus
}

export interface PolicyInfo {
  hotel_id: string
  hotel_name: string
  general_info: string
  cancellation_policy: CancellationPolicy
  pet_policy: string
  pet_policy_source: 'amenities' | 'not_provided'
  check_in_time: string | null
  check_out_time: string | null
  information_gaps: string[]
  data_source: string
  is_live: boolean
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  version: string
  provider: string
  currency: string
  data_source: string
  is_live: boolean
  mcp_server: {
    name: string
    connected: boolean
    tools: string[]
  }
}
