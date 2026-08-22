import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled'])
const POLL_INTERVAL_MS = 1500

// Polls the existing (unchanged) live-status endpoints — GET /jobs/<id> for an upload/retry,
// GET /crawl-jobs/<id> for a crawl — until the job reaches a terminal state. These are JobStore/
// CrawlJobStore's in-memory, ephemeral view (see A.4 in the plan); GET /ingestion-jobs is the
// separate, persisted history list used to render "recent uploads" across page reloads.
export function useJobPolling<T extends { status: string }>(
  jobId: string | null,
  kind: 'upload' | 'crawl',
  onSettled?: (status: T) => void,
) {
  const [status, setStatus] = useState<T | null>(null)
  const onSettledRef = useRef(onSettled)

  useEffect(() => {
    onSettledRef.current = onSettled
  }, [onSettled])

  useEffect(() => {
    setStatus(null)
    if (!jobId) return undefined

    let cancelled = false
    const path = kind === 'upload' ? `/jobs/${jobId}` : `/crawl-jobs/${jobId}`

    async function poll() {
      try {
        const result = await api.get<T>(path)
        if (cancelled) return
        setStatus(result)
        if (TERMINAL_STATUSES.has(result.status)) {
          onSettledRef.current?.(result)
          return
        }
      } catch {
        if (cancelled) return
      }
      if (!cancelled) setTimeout(poll, POLL_INTERVAL_MS)
    }

    void poll()
    return () => {
      cancelled = true
    }
  }, [jobId, kind])

  return status
}
