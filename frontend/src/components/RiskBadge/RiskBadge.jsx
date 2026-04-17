const CONFIG = {
  insider: {
    label: 'INSIDER',
    className: 'bg-insider/20 text-insider border border-insider/40',
  },
  suspicious: {
    label: 'SUSPICIOUS',
    className: 'bg-suspicious/20 text-suspicious border border-suspicious/40',
  },
  clean: {
    label: 'CLEAN',
    className: 'bg-clean/20 text-clean border border-clean/40',
  },
  pending: {
    label: 'PENDING',
    className: 'bg-surface2 text-muted border border-border animate-pulse',
  },
}

export default function RiskBadge({ level, size = 'sm' }) {
  const config = CONFIG[level] ?? CONFIG.pending
  const sizeClass = size === 'lg' ? 'px-3 py-1.5 text-sm' : 'px-2 py-0.5 text-xs'

  return (
    <span
      className={`inline-flex items-center font-mono font-semibold tracking-wider rounded ${sizeClass} ${config.className}`}
    >
      {config.label}
    </span>
  )
}
