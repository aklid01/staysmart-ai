import type { ChatResponse, HealthResponse, HotelDetailsPayload, PolicyInfo } from './types'

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
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
      0,
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
    throw new ApiError(code, message, response.status)
  }
  return (await response.json()) as T
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export interface ChatRequestBody {
  message: string
  conversation_id: string
  history: { role: 'user' | 'assistant'; content: string }[]
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
