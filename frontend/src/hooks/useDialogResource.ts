import { useEffect, useState } from 'react'
import { ApiError } from '../api'

export function useDialogResource<T>(
  key: string,
  fetcher: () => Promise<T>,
): { payload: T | null; error: ApiError | null } {
  const [payload, setPayload] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    let cancelled = false
    fetcher()
      .then((result) => {
        if (!cancelled) setPayload(result)
      })
      .catch((exc: ApiError) => {
        if (!cancelled) setError(exc)
      })
    return () => {
      cancelled = true
    }
  }, [key])

  return { payload, error }
}
