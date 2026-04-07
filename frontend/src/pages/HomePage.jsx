import { useState, useEffect } from 'react'
import SearchInput from '../components/SearchInput/SearchInput'
import MarketCard from '../components/MarketCard/MarketCard'
import { getAlerts } from '../services/api'

export default function HomePage() {
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAlerts()
      .then((alerts) => {
        // Extract unique markets from flagged alerts
        const seen = new Set()
        const unique = []
        for (const alert of alerts) {
          if (alert.market && !seen.has(alert.market.conditionId)) {
            seen.add(alert.market.conditionId)
            unique.push(alert.market)
          }
        }
        setMarkets(unique)
      })
      .catch(() => setMarkets([]))
      .finally(() => setLoading(false))
  }, [])

  const flagged = markets.filter((m) => m.verdict !== 'clean')
  const all = markets

  return (
    <div className="dot-grid min-h-[calc(100vh-120px)] flex flex-col items-center justify-start pt-20 pb-16">
      {/* Hero */}
      <div className="text-center mb-10 max-w-2xl">
        <div className="flex items-center justify-center gap-3 mb-4">
          <h1 className="text-4xl sm:text-5xl font-headline font-bold text-white tracking-tight">
            Is this market being manipulated?
          </h1>
        </div>
        <p className="text-muted font-body text-base">
          Paste a Polymarket URL or search any market to detect insider trading
          signals in real time.
        </p>
      </div>

      {/* Search */}
      <div className="w-full max-w-2xl mb-16 px-4">
        <SearchInput autoFocus />
        {markets.length > 0 && (
          <div className="flex flex-wrap items-center gap-3 mt-3 px-1">
            <span className="text-muted text-xs font-data">Try:</span>
            {markets.slice(0, 2).map((m) => (
              <button
                key={m.conditionId}
                className="text-xs text-muted hover:text-brand font-data underline decoration-dotted transition-colors"
                onClick={() => { window.location.href = `/market/${m.conditionId}` }}
              >
                "{m.question.slice(0, 40)}..."
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Market sections */}
      <div className="w-full max-w-5xl px-4">
        {loading ? (
          <div className="flex items-center justify-center h-32 gap-3 text-muted">
            <span className="w-4 h-4 border-2 border-muted border-t-brand rounded-full animate-spin" />
            <span className="font-data text-sm">Loading detected markets...</span>
          </div>
        ) : markets.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-muted font-data text-sm mb-2">No flagged markets yet.</p>
            <p className="text-muted font-data text-xs">
              Search for a market above to start insider detection.
            </p>
          </div>
        ) : (
          <>
            {flagged.length > 0 && (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-white font-headline font-semibold text-lg">
                    Recently Detected
                  </h2>
                  <span className="flex items-center gap-1.5 text-xs font-data text-muted">
                    <span className="w-1.5 h-1.5 rounded-full bg-brand pulse-dot inline-block" />
                    Live
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
                  {flagged.map((market) => (
                    <MarketCard key={market.conditionId} market={market} />
                  ))}
                </div>
              </>
            )}

            <h2 className="text-white font-headline font-semibold text-lg mb-4">
              All Markets
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {all.map((market) => (
                <MarketCard key={market.conditionId} market={market} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
