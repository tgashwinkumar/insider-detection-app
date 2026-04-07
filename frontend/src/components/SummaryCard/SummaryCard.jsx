export default function SummaryCard({ label, value, sub, accent = 'brand', icon }) {
  const accentColor = {
    brand: 'text-brand',
    insider: 'text-insider',
    suspicious: 'text-suspicious',
    clean: 'text-clean',
    yes: 'text-yes',
    muted: 'text-muted',
  }[accent] || 'text-brand'

  return (
    <div className="bg-surface1 border border-border rounded p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-muted text-xs font-data uppercase tracking-wider">{label}</span>
        {icon && <span className="text-xl">{icon}</span>}
      </div>
      <span className={`text-3xl font-headline font-bold ${accentColor}`}>{value}</span>
      {sub && <span className="text-muted text-xs font-data">{sub}</span>}
    </div>
  )
}
