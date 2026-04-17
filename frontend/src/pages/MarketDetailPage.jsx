import { useMemo, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTradeData } from '../hooks/useTradeData'
import { useMarketWebSocket } from '../hooks/useMarketWebSocket'
import VerdictBanner from '../components/VerdictBanner/VerdictBanner'
import SummaryCard from '../components/SummaryCard/SummaryCard'
import TimelineBar from '../components/TimelineBar/TimelineBar'
import TradeTable from '../components/TradeTable/TradeTable'
import { formatUsdc, formatDate } from '../utils/formatters'

export default function MarketDetailPage() {
  const { conditionId } = useParams()
  const { data, loading, error, ingestStatus, hasPendingScores, refreshTrades } = useTradeData(conditionId)
  const { pendingLiveTrades, newLiveTrades, connected: liveConnected } = useMarketWebSocket(conditionId)

  // When a new scored trade arrives via WebSocket, also refresh the API data
  // so data.trades stays in sync (handles the case where score polling has stopped).
  const prevNewLiveCount = useRef(0)
  useEffect(() => {
    if (newLiveTrades.length > prevNewLiveCount.current) {
      prevNewLiveCount.current = newLiveTrades.length
      refreshTrades()
    }
  }, [newLiveTrades.length, refreshTrades])

  // Merge live trades (from WS) on top of polled trades, deduplicating by id
  const trades = useMemo(() => {
    const base = data?.trades ?? []
    if (!newLiveTrades.length) return base
    const existingIds = new Set(base.map((t) => t.id))
    const fresh = newLiveTrades.filter((t) => !existingIds.has(t.id))
    return [...fresh, ...base]
  }, [data?.trades, newLiveTrades])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-muted">
          <span className="w-5 h-5 border-2 border-muted border-t-brand rounded-full animate-spin" />
          <span className="font-data text-sm">Analyzing market...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-insider font-data text-sm mb-4">Failed to load market data</p>
        <Link to="/" className="text-brand text-sm font-data hover:underline">← Back to search</Link>
      </div>
    )
  }

  if (!data) return null

  const { market, verdict, summary } = data

  return (
    <div className="flex flex-col gap-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs font-data text-muted">
        <Link to="/" className="hover:text-white transition-colors">Search</Link>
        <span>›</span>
        <span className="text-white line-clamp-1">{market.question}</span>
      </div>

      {/* Verdict banner */}
      <VerdictBanner
        verdict={verdict.level}
        direction={verdict.direction}
        confidence={verdict.confidence}
        subtitle={
          verdict.level === 'insider'
            ? `${summary.flaggedCount} wallets with insider profile placed large ${verdict.direction?.toUpperCase()} positions close to market close.`
            : verdict.level === 'suspicious'
            ? 'Some trades show unusual timing or concentration patterns. Monitor closely.'
            : 'No statistically significant insider patterns detected in this market.'
        }
      />

      {/* Market info strip */}
      <div className="flex flex-wrap items-center gap-4 px-4 py-2.5 bg-surface1 border border-border rounded text-xs font-data">
        <span className="text-white font-semibold line-clamp-1 flex-1">{market.question}</span>
        <span className="text-muted">Closes {formatDate(market.resolutionDate)}</span>
        <span className="text-muted">Vol: {formatUsdc(market.volume)}</span>
        <span className="text-muted">{market.traderCount} traders</span>
        <span className={`font-semibold ${market.manipulability > 0.7 ? 'text-insider' : market.manipulability > 0.4 ? 'text-suspicious' : 'text-clean'}`}>
          Manipulability: {Math.round(market.manipulability * 100)}%
        </span>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <SummaryCard
          label="Total Trades"
          value={summary.totalTrades}
          icon="📊"
          accent="muted"
        />
        <SummaryCard
          label="Unique Wallets"
          value={summary.uniqueWallets}
          icon="👛"
          accent="muted"
        />
        <SummaryCard
          label="Flagged Insider"
          value={summary.flaggedCount}
          icon="⚠"
          accent="insider"
          sub="confirmed insider trades"
        />
        <SummaryCard
          label="Highest Score"
          value={`${Math.round(summary.highestScore * 100)}/100`}
          icon="🎯"
          accent={summary.highestScore >= 0.9 ? 'insider' : summary.highestScore >= 0.8 ? 'suspicious' : 'clean'}
        />
      </div>

      {/* Timeline */}
      <TimelineBar trades={data?.trades ?? []} resolutionDate={market.resolutionDate} />

      {/* Trades table or ingestion progress */}
      <div>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-white font-headline font-semibold text-base">
            All Trades — Insider Classification
          </h2>
          {liveConnected && (
            <span className="flex items-center gap-1.5 text-xs font-data text-clean">
              <span className="w-1.5 h-1.5 rounded-full bg-clean animate-pulse" />
              Live
            </span>
          )}
        </div>
        {/* Ingestion progress bar — shown while fetching, but doesn't block trade table */}
        {ingestStatus?.isActive && (
          <div className="bg-surface1 border border-border rounded p-4 flex items-center justify-between mb-4">
            <div className="flex items-center gap-3 text-brand">
              <span className="w-4 h-4 border-2 border-muted border-t-brand rounded-full animate-spin" />
              <span className="font-data text-sm">
                {ingestStatus.status === 'pending' ? 'Queued for indexing…' : 'Indexing trades from blockchain…'}
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs font-mono text-muted">
              <span>{ingestStatus.tradesIndexed} indexed</span>
              <span>·</span>
              <span>{ingestStatus.walletsFound} wallets</span>
              <span>·</span>
              <span>batch {ingestStatus.batchesProcessed}</span>
            </div>
          </div>
        )}

        {ingestStatus?.isFailed && (
          <div className="bg-surface1 border border-border rounded p-4 text-center mb-4">
            <p className="text-insider text-sm font-data mb-1">Ingestion failed</p>
            <p className="text-muted text-xs font-mono">{ingestStatus.error}</p>
          </div>
        )}

        {/* Pending live trade placeholders (trade seen on Polymarket WS, not yet scored) */}
        {pendingLiveTrades.length > 0 && (
          <div className="mb-2 flex flex-col gap-1">
            {pendingLiveTrades.map((p) => (
              <div
                key={`${p.asset_id}-${p.timestamp}`}
                className="flex items-center gap-3 px-4 py-2.5 bg-surface1 border border-border rounded text-xs font-data text-muted animate-pulse"
              >
                <span className="w-2 h-2 rounded-full bg-brand animate-ping" />
                <span>
                  Live trade detected — {p.side} {parseFloat(p.size).toFixed(0)} shares
                  @ ${parseFloat(p.price).toFixed(2)} — scoring in progress…
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Trade table — shown as soon as any trades exist, even during ingestion */}
        {trades.length > 0 ? (
          <>
            <p className="text-muted text-xs font-data mb-4">
              Click any row to view the wallet's full insider score breakdown.
            </p>
            <TradeTable trades={trades} hasPendingScores={hasPendingScores} />
          </>
        ) : !ingestStatus?.isActive && (
          <div className="bg-surface1 border border-border rounded p-10 text-center text-muted text-sm font-data">
            No trades found for this market.
          </div>
        )}
      </div>
    </div>
  )
}
