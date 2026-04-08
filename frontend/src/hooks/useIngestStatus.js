import { useState, useEffect, useRef } from 'react'
import { getIngestStatus } from '../services/api'

const TERMINAL_STATUSES = ['done', 'failed']

/**
 * Polls GET /api/ingest/{conditionId}/status every `intervalMs` ms.
 * Stops automatically when status reaches "done" or "failed".
 * Pass null conditionId to disable.
 */
export function useIngestStatus(conditionId, intervalMs = 10000) {
  const [job, setJob] = useState(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!conditionId) {
      setJob(null)
      return
    }

    let cancelled = false

    const poll = async () => {
      try {
        const data = await getIngestStatus(conditionId)
        if (!cancelled) {
          setJob(data)
          if (TERMINAL_STATUSES.includes(data?.status)) {
            clearInterval(intervalRef.current)
          }
        }
      } catch {
        // 404 means job not created in Redis yet — keep polling
      }
    }

    poll() // fire immediately on mount
    intervalRef.current = setInterval(poll, intervalMs)

    return () => {
      cancelled = true
      clearInterval(intervalRef.current)
    }
  }, [conditionId, intervalMs])

  return {
    status: job?.status ?? null,
    tradesIndexed: job?.tradesIndexed ?? 0,
    walletsFound: job?.walletsFound ?? 0,
    batchesProcessed: job?.batchesProcessed ?? 0,
    error: job?.error ?? null,
    warnings: job?.warnings ?? [],
    isComplete: job?.status === 'done',
    isFailed: job?.status === 'failed',
    isActive: job?.status === 'pending' || job?.status === 'running',
  }
}
