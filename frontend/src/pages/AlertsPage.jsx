import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import RiskBadge from '../components/RiskBadge/RiskBadge'
import FactorChip from '../components/FactorChip/FactorChip'
import WalletScorePanel from '../components/WalletScorePanel/WalletScorePanel'
import { getAlerts } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { truncateAddress, formatUsdc, formatTimeAgo } from '../utils/formatters'
import { KNOWN_WALLETS } from '../utils/constants'

const SORT_OPTIONS = [
  { value: 'score', label: 'Insider Score' },
  { value: 'time', label: 'Most Recent' },
  { value: 'size', label: 'Trade Size' },
]

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([])
  const [loadingAlerts, setLoadingAlerts] = useState(true)
  const [apiError, setApiError] = useState(null)
  const [sortBy, setSortBy] = useState('score')
  const [filterLevel, setFilterLevel] = useState('all')
  const [selectedTrade, setSelectedTrade] = useState(null)

  // WebSocket: receive live alerts pushed from Redis pub/sub
  const { data: wsData, connected: wsConnected } = useWebSocket('/trades')

  // Load initial alerts from API
  useEffect(() => {
    getAlerts()
      .then(setAlerts)
      .catch((e) => setApiError(e.message))
      .finally(() => setLoadingAlerts(false))
  }, [])

  // Prepend live WebSocket alerts (ignore pings)
  useEffect(() => {
    if (wsData && wsData.type !== 'ping' && wsData.id) {
      setAlerts((prev) => {
        const exists = prev.some((a) => a.id === wsData.id)
        return exists ? prev : [wsData, ...prev]
      })
    }
  }, [wsData])

  const filtered = alerts
    .filter((a) => filterLevel === 'all' || a.classification === filterLevel)
    .sort((a, b) => {
      if (sortBy === 'score') return b.insiderScore - a.insiderScore
      if (sortBy === 'time') return b.timestamp - a.timestamp
      if (sortBy === 'size') return b.sizeUsdc - a.sizeUsdc
      return 0
    })

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-headline font-bold text-white mb-1">Live Alerts</h1>
          <p className="text-muted text-sm font-data">
            Flagged trades detected across all Polymarket markets in real time.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs font-data text-muted bg-surface1 px-3 py-1.5 rounded border border-border">
          <span className={`w-1.5 h-1.5 rounded-full inline-block ${wsConnected ? 'bg-brand pulse-dot' : 'bg-muted'}`} />
          {wsConnected ? 'Live feed' : 'Connecting...'}
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Filter */}
        <div className="flex items-center gap-1 bg-surface1 border border-border rounded p-1">
          {['all', 'insider', 'suspicious'].map((f) => (
            <button
              key={f}
              onClick={() => setFilterLevel(f)}
              className={`px-3 py-1 rounded text-xs font-data capitalize transition-colors
                ${filterLevel === f ? 'bg-surface2 text-white' : 'text-muted hover:text-white'}`}
            >
              {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-muted text-xs font-data">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-surface1 border border-border rounded px-2 py-1 text-xs font-data text-white outline-none focus:border-brand"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Alert count / loading / error */}
      {loadingAlerts ? (
        <div className="flex items-center gap-2 text-muted text-xs font-data -mt-3">
          <span className="w-3 h-3 border border-muted border-t-brand rounded-full animate-spin" />
          Loading alerts...
        </div>
      ) : apiError ? (
        <p className="text-insider text-xs font-data -mt-3">Failed to load alerts: {apiError}</p>
      ) : (
        <p className="text-muted text-xs font-data -mt-3">
          {filtered.length} alert{filtered.length !== 1 ? 's' : ''}
        </p>
      )}

      {/* Alerts table */}
      <div className="bg-surface1 border border-border rounded overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                {['Level', 'Wallet', 'Market', 'Size', 'Direction', 'Score', 'Factors', 'Time', ''].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-2.5 text-left text-xs font-data font-semibold text-muted uppercase tracking-wider whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((alert) => {
                const label = KNOWN_WALLETS[alert.wallet]
                const isSelected = selectedTrade?.id === alert.id
                const borderColor =
                  alert.classification === 'insider'
                    ? 'border-l-insider'
                    : alert.classification === 'suspicious'
                    ? 'border-l-suspicious'
                    : 'border-l-clean'

                return (
                  <tr
                    key={alert.id}
                    className={`border-l-2 ${borderColor} cursor-pointer transition-colors
                      ${isSelected ? 'bg-surface2' : 'hover:bg-surface2/60'}`}
                    onClick={() => setSelectedTrade(isSelected ? null : alert)}
                  >
                    <td className="px-4 py-3">
                      <RiskBadge level={alert.classification} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col">
                        {label && <span className="text-brand text-xs font-mono font-semibold">{label}</span>}
                        <span className="text-muted text-xs font-mono">{truncateAddress(alert.wallet)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 max-w-[200px]">
                      <Link
                        to={`/market/${alert.market?.conditionId}`}
                        className="text-white text-xs font-body hover:text-brand transition-colors line-clamp-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {alert.market?.question}
                      </Link>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <span className="text-white font-mono text-sm font-semibold">{formatUsdc(alert.sizeUsdc)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                          alert.direction === 'yes' ? 'bg-yes/15 text-yes' : 'bg-no/15 text-no'
                        }`}
                      >
                        {alert.direction?.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`font-mono text-sm font-bold ${
                          alert.insiderScore >= 0.7 ? 'text-insider' : 'text-suspicious'
                        }`}
                      >
                        {Math.round(alert.insiderScore * 100)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(alert.factors).map(([key, score]) => (
                          <FactorChip key={key} factor={key} score={score} />
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className="text-muted text-xs font-mono">{formatTimeAgo(alert.timestamp)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-muted text-sm">›</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selectedTrade && (
        <WalletScorePanel trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
      )}
    </div>
  )
}
