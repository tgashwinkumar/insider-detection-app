import RiskBadge from '../RiskBadge/RiskBadge'
import FactorChip from '../FactorChip/FactorChip'
import { truncateAddress, formatUsdc, formatTimestamp } from '../../utils/formatters'
import { KNOWN_WALLETS } from '../../utils/constants'

const BORDER_COLOR = {
  insider: 'border-l-insider',
  suspicious: 'border-l-suspicious',
  clean: 'border-l-clean',
}

export default function TradeRow({ trade, onClick, isSelected }) {
  const label = KNOWN_WALLETS[trade.wallet]

  return (
    <tr
      className={`border-l-2 ${BORDER_COLOR[trade.classification]} cursor-pointer transition-colors
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
        </div>
      </td>

      {/* Time */}
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="text-muted text-xs font-mono">{formatTimestamp(trade.timestamp)}</span>
      </td>

      {/* Size */}
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
        <span
          className={`font-mono text-sm font-bold ${
            trade.insiderScore >= 0.7
              ? 'text-insider'
              : trade.insiderScore >= 0.45
              ? 'text-suspicious'
              : 'text-clean'
          }`}
        >
          {Math.round(trade.insiderScore * 100)}
        </span>
      </td>

      {/* Factors */}
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {Object.entries(trade.factors).map(([key, score]) => (
            <FactorChip key={key} factor={key} score={score} />
          ))}
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
