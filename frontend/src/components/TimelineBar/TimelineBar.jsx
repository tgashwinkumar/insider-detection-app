import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { formatUsdc, formatTimestamp } from '../../utils/formatters'

const RISK_COLORS = {
  insider: '#EF4444',
  suspicious: '#F59E0B',
  clean: '#22C55E',
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-surface2 border border-border rounded p-3 text-xs font-data shadow-xl">
      <p className="text-muted mb-1">{formatTimestamp(d.time)}</p>
      <p className="text-white font-semibold">{formatUsdc(d.size)}</p>
      <p className={d.classification === 'insider' ? 'text-insider' : d.classification === 'suspicious' ? 'text-suspicious' : 'text-clean'}>
        {d.classification.toUpperCase()}
      </p>
      {d.wallet && (
        <p className="text-muted mt-1">{d.wallet.slice(0, 8)}...{d.wallet.slice(-4)}</p>
      )}
    </div>
  )
}

function CustomDot(props) {
  const { cx, cy, payload } = props
  const color = RISK_COLORS[payload.classification] || '#6B7280'
  const r = payload.classification === 'insider' ? 8 : payload.classification === 'suspicious' ? 6 : 4
  return (
    <g>
      {payload.classification === 'insider' && (
        <circle cx={cx} cy={cy} r={r + 4} fill={color} opacity={0.15} />
      )}
      <circle cx={cx} cy={cy} r={r} fill={color} stroke="#0C0C0E" strokeWidth={1.5} />
    </g>
  )
}

export default function TimelineBar({ trades, resolutionDate }) {
  const data = trades.map((t) => ({
    time: t.timestamp,
    size: t.sizeUsdc,
    classification: t.classification,
    wallet: t.wallet,
    direction: t.direction,
  }))

  const resolutionTimestamp = resolutionDate ? new Date(resolutionDate).getTime() : null

  const insiderData = data.filter((d) => d.classification === 'insider')
  const suspiciousData = data.filter((d) => d.classification === 'suspicious')
  const cleanData = data.filter((d) => d.classification === 'clean')

  const minTime = Math.min(...data.map((d) => d.time))
  const maxTime = Math.max(...data.map((d) => d.time), resolutionTimestamp || 0)

  return (
    <div className="bg-surface1 border border-border rounded p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-headline font-semibold text-sm">
          Insider Activity Timeline
        </h3>
        <div className="flex items-center gap-4 text-xs font-data">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-insider inline-block" />
            <span className="text-muted">Insider</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-suspicious inline-block" />
            <span className="text-muted">Suspicious</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-clean inline-block" />
            <span className="text-muted">Clean</span>
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2A2A32" />
          <XAxis
            dataKey="time"
            type="number"
            domain={[minTime - 3600000, maxTime + 3600000]}
            scale="time"
            tickFormatter={(t) => {
              const d = new Date(t)
              return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`
            }}
            tick={{ fill: '#6B7280', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            axisLine={{ stroke: '#2A2A32' }}
            tickLine={false}
          />
          <YAxis
            dataKey="size"
            tickFormatter={(v) => formatUsdc(v)}
            tick={{ fill: '#6B7280', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            axisLine={{ stroke: '#2A2A32' }}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#2A2A32' }} />

          {resolutionTimestamp && (
            <ReferenceLine
              x={resolutionTimestamp}
              stroke="#EF4444"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{ value: 'Market Close', fill: '#EF4444', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            />
          )}

          <Scatter name="insider" data={insiderData} shape={<CustomDot />} />
          <Scatter name="suspicious" data={suspiciousData} shape={<CustomDot />} />
          <Scatter name="clean" data={cleanData} shape={<CustomDot />} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
