import type {
  ChatResponse,
  HealthResponse,
  HistoryEntry,
  HotelDetailsPayload,
  PolicyInfo,
} from './types'

export class ApiError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError(
      'network_error',
      'Cannot reach the StaySmart API. Is the backend running on port 8000?',
    )
  }
  if (!response.ok) {
    let code = 'http_error'
    let message = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
      }
    } catch {
      // keep defaults for non-JSON error bodies
    }
    throw new ApiError(code, message)
  }
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('malformed_response', `Request to ${path} returned a malformed JSON body`)
  }
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export interface ChatRequestBody {
  message: string
  conversation_id: string
  history: HistoryEntry[]
}

export function postChat(body: ChatRequestBody): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getHotelDetails(
  hotelId: string,
  stay?: { check_in: string; check_out: string },
): Promise<HotelDetailsPayload> {
  const params = new URLSearchParams()
  if (stay) {
    params.set('check_in', stay.check_in)
    params.set('check_out', stay.check_out)
  }
  const query = params.toString()
  return request<HotelDetailsPayload>(
    `/hotels/${encodeURIComponent(hotelId)}${query ? `?${query}` : ''}`,
  )
}

export function getHotelPolicies(hotelId: string): Promise<PolicyInfo> {
  return request<PolicyInfo>(`/hotels/${encodeURIComponent(hotelId)}/policies`)
}
