import { useState, useEffect } from 'react'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { truncateAddress, formatUsdc, formatDate } from '../../utils/formatters'
import { KNOWN_WALLETS } from '../../utils/constants'
import FactorChip from '../FactorChip/FactorChip'
import { getWalletScore } from '../../services/api'

const FACTOR_DISPLAY = [
  { key: 'entryTiming', label: 'Entry Timing' },
  { key: 'marketCount', label: 'Market Count' },
  { key: 'tradeSize', label: 'Trade Size' },
  { key: 'walletAge', label: 'Wallet Age' },
  { key: 'concentration', label: 'Concentration' },
]

function ScoreBar({ label, score }) {
  const pct = Math.round(score * 100)
  const color =
    score >= 0.8 ? 'bg-insider' : score >= 0.6 ? 'bg-suspicious' : 'bg-clean'
  const textColor =
    score >= 0.8 ? 'text-insider' : score >= 0.6 ? 'text-suspicious' : 'text-clean'

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs font-data">
        <span className="text-muted">{label}</span>
        <span className={`font-mono font-semibold ${textColor}`}>{pct}/100</span>
      </div>
      <div className="h-1.5 bg-surface2 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function WalletScorePanel({ trade, onClose }) {
  const [walletData, setWalletData] = useState(null)

  // Fetch full wallet profile whenever the selected trade changes
  useEffect(() => {
    if (!trade?.wallet) return
    setWalletData(null)
    getWalletScore(trade.wallet)
      .then(setWalletData)
      .catch(() => {}) // silently fail — panel still works from trade prop
  }, [trade?.wallet])

  if (!trade) return null

  const label = KNOWN_WALLETS[trade.wallet]
  // Use wallet-level factors if available (averaged across all trades), else fall back to trade-level
  const factors = walletData?.factors || trade.factors
  const radarData = FACTOR_DISPLAY.map(({ key, label }) => ({
    factor: label,
    score: Math.round((factors[key] || 0) * 100),
  }))

  const scoreColor =
    trade.insiderScore >= 0.7
      ? 'text-insider'
      : trade.insiderScore >= 0.45
      ? 'text-suspicious'
      : 'text-clean'

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div
        className="relative w-full max-w-md h-full bg-surface1 border-l border-border overflow-y-auto slide-in-panel"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-surface1 border-b border-border p-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              {label && (
                <span className="text-brand font-mono text-sm font-semibold">{label}</span>
              )}
            </div>
            <p className="text-muted text-xs font-mono mt-0.5">{truncateAddress(trade.wallet, 10, 6)}</p>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-white transition-colors text-xl leading-none"
          >
            ✕
          </button>
        </div>

        <div className="p-4 flex flex-col gap-5">
          {/* Overall score */}
          <div className="bg-surface2 rounded p-4 flex items-center justify-between">
            <div>
              <p className="text-muted text-xs font-data uppercase tracking-wider mb-1">Insider Score</p>
              <p className={`text-4xl font-headline font-bold ${scoreColor}`}>
                {Math.round(trade.insiderScore * 100)}
                <span className="text-muted text-xl">/100</span>
              </p>
            </div>
            <div className="flex flex-col gap-1 text-right">
              <span
                className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                  trade.direction === 'yes'
                    ? 'bg-yes/15 text-yes border border-yes/30'
                    : 'bg-no/15 text-no border border-no/30'
                }`}
              >
                Bet {trade.direction?.toUpperCase()}
              </span>
              <span className="text-muted text-xs font-data">{formatUsdc(trade.sizeUsdc)}</span>
            </div>
          </div>

          {/* Radar chart */}
          <div>
            <p className="text-white text-sm font-headline font-semibold mb-3">Factor Breakdown</p>
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
                <PolarGrid stroke="#2A2A32" />
                <PolarAngleAxis
                  dataKey="factor"
                  tick={{ fill: '#6B7280', fontSize: 10, fontFamily: 'IBM Plex Sans' }}
                />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke="#EF4444"
                  fill="#EF4444"
                  fillOpacity={0.25}
                  strokeWidth={2}
                />
                <Tooltip
                  contentStyle={{
                    background: '#1C1C22',
                    border: '1px solid #2A2A32',
                    borderRadius: '4px',
                    fontFamily: 'IBM Plex Mono',
                    fontSize: 12,
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Wallet-level stats (from /api/wallets/{address}/score) */}
          {walletData && (
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Total Trades', value: walletData.totalTrades },
                { label: 'Markets Traded', value: walletData.marketsTraded },
                { label: 'Total Volume', value: formatUsdc(walletData.totalVolumeUsdc) },
                { label: 'Wallet Age', value: walletData.walletAgeDays != null ? `${walletData.walletAgeDays}d` : '—' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-surface2 rounded p-2.5">
                  <p className="text-muted text-xs font-data">{label}</p>
                  <p className="text-white text-sm font-mono font-semibold mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Score bars */}
          <div className="flex flex-col gap-3">
            {FACTOR_DISPLAY.map(({ key, label }) => (
              <ScoreBar key={key} label={label} score={factors[key] || 0} />
            ))}
          </div>

          {/* Active factor chips */}
          <div>
            <p className="text-muted text-xs font-data uppercase tracking-wider mb-2">Triggered Factors</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(trade.factors).map(([key, score]) => (
                <FactorChip key={key} factor={key} score={score} />
              ))}
            </div>
          </div>

          {/* Wallet timeline */}
          <div>
            <p className="text-white text-sm font-headline font-semibold mb-3">Wallet Timeline</p>
            <div className="relative flex flex-col gap-0">
              {[
                { label: 'Wallet Created', date: trade.walletCreatedAt, color: 'bg-muted' },
                { label: 'First Trade', date: trade.firstTradeAt, color: 'bg-suspicious' },
                { label: 'This Trade', date: trade.timestamp, color: 'bg-insider' },
              ].map(({ label, date, color }, i) => (
                <div key={i} className="flex items-start gap-3 pb-4 last:pb-0">
                  <div className="flex flex-col items-center">
                    <div className={`w-2.5 h-2.5 rounded-full ${color} mt-1 shrink-0`} />
                    {i < 2 && <div className="w-px flex-1 bg-border mt-1" style={{ minHeight: 24 }} />}
                  </div>
                  <div>
                    <p className="text-white text-xs font-data">{label}</p>
                    <p className="text-muted text-xs font-mono">
                      {date ? formatDate(new Date(date).toISOString().split('T')[0]) : '—'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* External link */}
          <a
            href={`https://polygonscan.com/address/${trade.wallet}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 py-2 px-4 border border-border rounded text-muted text-xs font-data hover:text-white hover:border-brand/40 transition-colors"
          >
            View on Polygonscan ↗
          </a>
        </div>
      </div>
    </div>
  )
}
