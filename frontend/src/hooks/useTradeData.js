import { useState, useEffect, useCallback, useRef } from 'react'
import { getMarketTrades, startIngest } from '../services/api'
import { useIngestStatus } from './useIngestStatus'

// Statuses that mean ingestion is in progress or not yet started
const ACTIVE_STATUSES = ['starting', 'pending', 'running']

// Phase 2: poll for score updates after ingestion finishes
const SCORE_POLL_INTERVAL_MS = 10000
const SCORE_POLL_MAX_ATTEMPTS = 40  // ~2 minutes max

export function useTradeData(conditionId) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // Phase 1: ingest polling
  const [pollingId, setPollingId] = useState(null)
  // Phase 2: score completion polling
  const scoreTimerRef = useRef(null)
  const scoreAttemptsRef = useRef(0)

  const ingestStatus = useIngestStatus(pollingId)

  const stopScorePolling = useCallback(() => {
    if (scoreTimerRef.current) {
      clearInterval(scoreTimerRef.current)
      scoreTimerRef.current = null
    }
    scoreAttemptsRef.current = 0
  }, [])

  const fetchTrades = useCallback(async () => {
    if (!conditionId) return
    setLoading(true)
    setError(null)
    try {
      const result = await getMarketTrades(conditionId)
      setData(result)

      const ingestState = result.ingestion?.status
      if (!result.trades?.length && ACTIVE_STATUSES.includes(ingestState)) {
        if (ingestState === 'starting') {
          startIngest(conditionId).catch(() => {})
        }
        setPollingId(conditionId)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [conditionId])

  // Phase 2: silent background re-fetch (no loading spinner)
  const silentFetch = useCallback(async () => {
    if (!conditionId) return
    try {
      const result = await getMarketTrades(conditionId)
      setData(result)

      // Stop if all trades are scored (no nulls)
      const hasPending = result.trades?.some((t) => t.insiderScore === null)
      if (!hasPending) {
        stopScorePolling()
        return
      }

      scoreAttemptsRef.current += 1
      if (scoreAttemptsRef.current >= SCORE_POLL_MAX_ATTEMPTS) {
        stopScorePolling()
      }
    } catch {
      // silently ignore errors during score polling
    }
  }, [conditionId, stopScorePolling])

  // Phase 1 → Phase 2 transition: ingest done, start score polling
  useEffect(() => {
    if (ingestStatus.isComplete) {
      setPollingId(null)
      // Immediately fetch, then start score polling
      silentFetch().then(() => {
        stopScorePolling()
        scoreAttemptsRef.current = 0
        scoreTimerRef.current = setInterval(silentFetch, SCORE_POLL_INTERVAL_MS)
      })
    }
  }, [ingestStatus.isComplete]) // eslint-disable-line react-hooks/exhaustive-deps

  // Also start score polling when trades load with pending scores (already ingested)
  useEffect(() => {
    if (!data) return
    const hasPending = data.trades?.some((t) => t.insiderScore === null)
    if (hasPending && !scoreTimerRef.current && !pollingId) {
      scoreAttemptsRef.current = 0
      scoreTimerRef.current = setInterval(silentFetch, SCORE_POLL_INTERVAL_MS)
    }
    if (!hasPending) {
      stopScorePolling()
    }
  }, [data, pollingId, silentFetch, stopScorePolling])

  // Fetch on conditionId change; clean up score polling
  useEffect(() => {
    setData(null)
    setPollingId(null)
    stopScorePolling()
    fetchTrades()
    return () => stopScorePolling()
  }, [fetchTrades]) // eslint-disable-line react-hooks/exhaustive-deps

  const hasPendingScores = Boolean(data?.trades?.some((t) => t.insiderScore === null))

  // Called by useMarketWebSocket when a new_trade arrives — refreshes the
  // API data so data.trades stays in sync even when score polling has stopped.
  const refreshTrades = useCallback(async () => {
    if (!conditionId) return
    try {
      const result = await getMarketTrades(conditionId)
      setData(result)
    } catch {
      // non-fatal — the WS payload already has the trade data
    }
  }, [conditionId])

  return {
    data,
    loading,
    error,
    ingestStatus: pollingId ? ingestStatus : null,
    hasPendingScores,
    refreshTrades,
  }
}
