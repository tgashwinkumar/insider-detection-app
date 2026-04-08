import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { searchMarkets } from '../services/api'

// Matches a full 0x-prefixed 64-character hex string anywhere in the input
const EMBEDDED_ID_REGEX = /0x[0-9a-fA-F]{64}/i

/**
 * Transient page: resolves a URL / slug / text query to a real conditionId
 * then redirects to /market/{conditionId}. All ingestion + polling happens there.
 */
export default function SearchResolvePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const q = searchParams.get('q') || ''
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!q) {
      navigate('/', { replace: true })
      return
    }

    // If the query IS a bare condition ID, skip the API call entirely
    if (/^0x[0-9a-fA-F]{64}$/i.test(q.trim())) {
      navigate(`/market/${q.trim().toLowerCase()}`, { replace: true })
      return
    }

    // If the query CONTAINS a condition ID embedded in it (e.g. copy-pasted JSON
    // like `{condition_id: "0x9352..."}` ), extract it and navigate directly.
    const embedded = q.match(EMBEDDED_ID_REGEX)
    if (embedded) {
      navigate(`/market/${embedded[0].toLowerCase()}`, { replace: true })
      return
    }

    const apiBase = import.meta.env.VITE_API_URL 

    searchMarkets(q)
      .then((markets) => {
        if (markets.length > 0) {
          // Navigate to the first market; MarketDetailPage handles ingestion
          navigate(`/market/${markets[0].conditionId}`, { replace: true })
        } else {
          setError(`No markets found for: "${q.slice(0, 80)}"`)
        }
      })
      .catch((err) => {
        const isNetworkError = !err.message?.startsWith('API error')
        if (isNetworkError) {
          setError(`Cannot connect to backend at ${apiBase}. Is Docker running?`)
        } else {
          setError(`Search failed: ${err.message}`)
        }
      })
  }, [q, navigate])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-insider font-data text-sm">{error}</p>
        <Link to="/" className="text-brand text-sm font-data hover:underline">
          ← Back to search
        </Link>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex items-center gap-3 text-muted">
        <span className="w-5 h-5 border-2 border-muted border-t-brand rounded-full animate-spin" />
        <span className="font-data text-sm">Resolving market…</span>
      </div>
    </div>
  )
}
