import { FACTOR_LABELS, FACTOR_THRESHOLD } from '../../utils/constants'

const FACTOR_ICONS = {
  entryTiming: '⏱',
  marketCount: '📊',
  tradeSize: '💰',
  walletAge: '🆕',
  concentration: '🎯',
}

export default function FactorChip({ factor, score }) {
  if (score < FACTOR_THRESHOLD) return null

  const label = FACTOR_LABELS[factor] || factor
  const icon = FACTOR_ICONS[factor] || '•'
  const isHigh = score >= 0.8

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-data font-medium border
        ${isHigh
          ? 'bg-insider/10 text-insider border-insider/30'
          : 'bg-suspicious/10 text-suspicious border-suspicious/30'
        }`}
      title={`${label}: ${Math.round(score * 100)}/100`}
    >
      <span>{icon}</span>
      {label}
    </span>
  )
}
