import RiskBadge from '../RiskBadge/RiskBadge'
import FactorChip from '../FactorChip/FactorChip'
import { truncateAddress, formatUsdc, formatTimestamp } from '../../utils/formatters'
import { KNOWN_WALLETS } from '../../utils/constants'

const BORDER_COLOR = {
  insider: 'border-l-insider',
  suspicious: 'border-l-suspicious',
  clean: 'border-l-clean',
}

function scoreColor(score) {
  if (score === null || score === undefined) return 'text-muted'
  if (score >= 0.9) return 'text-insider'
  if (score >= 0.8) return 'text-suspicious'
  return 'text-clean'
}

export default function TradeRow({ trade, onClick, isSelected }) {
  const label = KNOWN_WALLETS[trade.wallet]
  const borderClass = BORDER_COLOR[trade.classification] ?? 'border-l-border'

  // walletAgeDays comes from factorSources (scored at trade time)
  const walletAgeDays = trade.factorSources?.walletAgeDays

  return (
    <tr
      className={`border-l-2 ${borderClass} cursor-pointer transition-colors
        ${isSelected ? 'bg-surface2' : 'hover:bg-surface2/60'}`}
      onClick={() => onClick(trade)}
    >
      {/* Classification */}
      <td className="px-4 py-3 whitespace-nowrap">
        <RiskBadge level={trade.classification} />
      </td>

      {/* Wallet */}
      <td className="px-4 py-3">
        <div className="flex flex-col">
          {label && <span className="text-brand text-xs font-mono font-semibold">{label}</span>}
          <span className="text-muted text-xs font-mono">{truncateAddress(trade.wallet)}</span>
          {walletAgeDays !== null && walletAgeDays !== undefined && (
            <span className="text-muted/60 text-xs font-data mt-0.5">
              {walletAgeDays < 1
                ? `${Math.round(walletAgeDays * 24)}h old`
                : `${Math.round(walletAgeDays)}d old`}
            </span>
          )}
        </div>
      </td>

      {/* Time */}
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="text-muted text-xs font-mono">{formatTimestamp(trade.timestamp)}</span>
      </td>

      {/* Size — factorSources.tradeSizeUsdc should match sizeUsdc */}
      <td className="px-4 py-3 whitespace-nowrap text-right">
        <span className="text-white font-mono text-sm font-semibold">{formatUsdc(trade.sizeUsdc)}</span>
      </td>

      {/* Direction */}
      <td className="px-4 py-3 whitespace-nowrap">
        <span
          className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
            trade.direction === 'yes'
              ? 'bg-yes/15 text-yes'
              : 'bg-no/15 text-no'
          }`}
        >
          {trade.direction?.toUpperCase()}
        </span>
      </td>

      {/* Insider score */}
      <td className="px-4 py-3 whitespace-nowrap text-right">
        {trade.insiderScore === null || trade.insiderScore === undefined ? (
          <span className="font-mono text-sm text-muted">—</span>
        ) : (
          <span className={`font-mono text-sm font-bold ${scoreColor(trade.insiderScore)}`}>
            {Math.round(trade.insiderScore * 100)}
          </span>
        )}
      </td>

      {/* Factors */}
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {trade.factors
            ? Object.entries(trade.factors).map(([key, score]) => (
                <FactorChip key={key} factor={key} score={score} />
              ))
            : <span className="text-muted/50 text-xs font-data italic">scoring…</span>
          }
        </div>
      </td>

      {/* Expand */}
      <td className="px-4 py-3 text-right">
        <span className={`text-muted text-sm transition-transform inline-block ${isSelected ? 'rotate-180' : ''}`}>
          ›
        </span>
      </td>
    </tr>
  )
}
