import { useNavigate } from 'react-router-dom'
import RiskBadge from '../RiskBadge/RiskBadge'
import { formatDate, formatUsdc } from '../../utils/formatters'

export default function MarketCard({ market }) {
  const navigate = useNavigate()
  const { conditionId, question, resolutionDate, verdict, direction, confidence, volume, traderCount } = market

  return (
    <div
      className="bg-surface1 border border-border rounded p-5 flex flex-col gap-3 hover:border-brand/40 transition-colors cursor-pointer group"
      onClick={() => navigate(`/market/${conditionId}`)}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <RiskBadge level={verdict} />
        <span className="text-muted text-xs font-data">Closes {formatDate(resolutionDate)}</span>
      </div>

      {/* Market question */}
      <p className="text-white font-body font-medium text-sm leading-snug line-clamp-2 group-hover:text-brand transition-colors">
        {question}
      </p>

      {/* Direction chip */}
      {direction && verdict !== 'clean' && (
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
              direction === 'yes'
                ? 'bg-yes/15 text-yes border border-yes/30'
                : 'bg-no/15 text-no border border-no/30'
            }`}
          >
            Smart money: {direction.toUpperCase()}
          </span>
          <span className="text-muted text-xs font-data">{Math.round(confidence)}% confidence</span>
        </div>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-4 pt-1 border-t border-border">
        <span className="text-muted text-xs font-data">{formatUsdc(volume)} vol</span>
        <span className="text-muted text-xs font-data">{traderCount} traders</span>
        <button
          className="ml-auto text-brand text-xs font-data hover:underline"
          onClick={(e) => {
            e.stopPropagation()
            navigate(`/market/${conditionId}`)
          }}
        >
          View Analysis →
        </button>
      </div>
    </div>
  )
}
