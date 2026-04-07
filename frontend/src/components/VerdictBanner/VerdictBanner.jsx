import { formatConfidence } from '../../utils/formatters'

const VERDICT_CONFIG = {
  insider: {
    label: 'INSIDER DETECTED',
    icon: '⚠',
    gradient: 'from-insider/20 via-insider/5 to-transparent',
    border: 'border-insider',
    text: 'text-insider',
  },
  suspicious: {
    label: 'SUSPICIOUS ACTIVITY',
    icon: '◉',
    gradient: 'from-suspicious/20 via-suspicious/5 to-transparent',
    border: 'border-suspicious',
    text: 'text-suspicious',
  },
  clean: {
    label: 'NO INSIDER SIGNAL',
    icon: '✓',
    gradient: 'from-clean/20 via-clean/5 to-transparent',
    border: 'border-clean',
    text: 'text-clean',
  },
}

export default function VerdictBanner({ verdict, direction, confidence, subtitle }) {
  const config = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.clean

  return (
    <div
      className={`relative rounded border-l-4 ${config.border} bg-gradient-to-r ${config.gradient} bg-surface1 p-6`}
    >
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          {/* Verdict label */}
          <div className="flex items-center gap-3 mb-2">
            <span className={`text-2xl font-headline font-bold ${config.text}`}>
              {config.icon} {config.label}
            </span>
          </div>

          {/* Direction + confidence */}
          <div className="flex items-center gap-3 mb-3">
            {direction && (
              <span
                className={`px-3 py-1 rounded font-mono font-bold text-sm ${
                  direction === 'yes'
                    ? 'bg-yes/20 text-yes border border-yes/40'
                    : 'bg-no/20 text-no border border-no/40'
                }`}
              >
                Smart money: {direction.toUpperCase()}
              </span>
            )}
            <span className="text-muted font-data text-sm">
              {formatConfidence(confidence)} confidence
            </span>
          </div>

          {subtitle && (
            <p className="text-muted text-sm font-body max-w-2xl">{subtitle}</p>
          )}
        </div>

        {/* Confidence gauge */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <div className="relative w-20 h-20">
            <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
              <circle cx="40" cy="40" r="32" fill="none" stroke="#2A2A32" strokeWidth="8" />
              <circle
                cx="40"
                cy="40"
                r="32"
                fill="none"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 32}`}
                strokeDashoffset={`${2 * Math.PI * 32 * (1 - confidence / 100)}`}
                className={
                  verdict === 'insider'
                    ? 'stroke-insider'
                    : verdict === 'suspicious'
                    ? 'stroke-suspicious'
                    : 'stroke-clean'
                }
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-lg font-mono font-bold ${config.text}`}>
                {Math.round(confidence)}%
              </span>
            </div>
          </div>
          <span className="text-muted text-xs font-data">confidence</span>
        </div>
      </div>
    </div>
  )
}
