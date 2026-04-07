import { useState, useEffect, useCallback } from 'react'
import { getMarketTrades, startIngest } from '../services/api'
import { useIngestStatus } from './useIngestStatus'

// Statuses that mean ingestion is in progress or not yet started
const ACTIVE_STATUSES = ['starting', 'pending', 'running']

export function useTradeData(conditionId) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // conditionId to poll — null means not polling
  const [pollingId, setPollingId] = useState(null)

  const ingestStatus = useIngestStatus(pollingId)

  const fetchTrades = useCallback(async () => {
    if (!conditionId) return
    setLoading(true)
    setError(null)
    try {
      const result = await getMarketTrades(conditionId)
      setData(result)

      const ingestState = result.ingestion?.status
      if (!result.trades?.length && ACTIVE_STATUSES.includes(ingestState)) {
        // "starting" means the backend fired a Celery dispatch but has no Redis
        // job yet — also call the ingest endpoint so a PENDING record exists
        // immediately (idempotent: guard skips it if already PENDING/RUNNING).
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

  // When polling finishes successfully, reload trades
  useEffect(() => {
    if (ingestStatus.isComplete) {
      setPollingId(null)
      fetchTrades()
    }
  }, [ingestStatus.isComplete]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch on conditionId change
  useEffect(() => {
    setData(null)
    setPollingId(null)
    fetchTrades()
  }, [fetchTrades])

  return {
    data,
    loading,
    error,
    // null when not polling; full status object while ingestion is in flight
    ingestStatus: pollingId ? ingestStatus : null,
  }
}
