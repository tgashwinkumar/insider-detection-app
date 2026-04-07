import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMarketSearch } from '../../hooks/useMarketSearch'
import RiskBadge from '../RiskBadge/RiskBadge'
import { formatDate } from '../../utils/formatters'

export default function SearchInput({ autoFocus = false, compact = false }) {
  const navigate = useNavigate()
  const { query, setQuery, queryType, results, loading } = useMarketSearch()
  const [open, setOpen] = useState(false)
  const inputRef = useRef(null)

  function handleSubmit(e) {
    e.preventDefault()
    if (!query.trim()) return

    // Exact condition ID — skip resolver, go straight to market page
    if (queryType === 'conditionId') {
      navigate(`/market/${query.trim().toLowerCase()}`)
      return
    }

    // Text query with a dropdown selection — navigate directly
    if (queryType === 'text' && results.length > 0) {
      navigate(`/market/${results[0].conditionId}`)
      return
    }

    // URL, tokenId, or text with no results — go to resolver which handles API call
    navigate(`/search?q=${encodeURIComponent(query.trim())}`)
  }

  function handleSelect(conditionId) {
    setOpen(false)
    navigate(`/market/${conditionId}`)
  }

  const showDropdown = open && query.length > 0 && results.length > 0

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <div
        className={`flex items-center bg-surface1 border rounded transition-colors
          ${open ? 'border-brand' : 'border-border hover:border-muted'}
          ${compact ? 'h-10' : 'h-14'}`}
      >
        {/* Search icon */}
        <span className="pl-4 text-muted text-lg">
          {loading ? (
            <span className="inline-block w-4 h-4 border-2 border-muted border-t-brand rounded-full animate-spin" />
          ) : (
            '⌕'
          )}
        </span>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          autoFocus={autoFocus}
          placeholder={compact ? 'Search markets...' : 'polymarket.com/event/... or search markets'}
          className={`flex-1 bg-transparent text-white placeholder-muted font-body outline-none px-3
            ${compact ? 'text-sm' : 'text-base'}`}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
        />

        {/* Query type indicator */}
        {queryType !== 'text' && query && (
          <span className="px-2 py-0.5 bg-surface2 text-muted text-xs font-mono rounded mr-2">
            {queryType}
          </span>
        )}

        {/* CTA */}
        <button
          type="submit"
          className={`bg-brand text-white font-headline font-semibold rounded-sm hover:bg-brand/90 transition-colors shrink-0
            ${compact ? 'px-3 py-1.5 text-sm mr-1' : 'px-5 py-2 mr-2 text-sm'}`}
        >
          Detect
        </button>
      </div>

      {/* Autocomplete dropdown */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-surface1 border border-border rounded shadow-2xl z-50 overflow-hidden">
          {results.map((market) => (
            <button
              key={market.conditionId}
              type="button"
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface2 text-left transition-colors border-b border-border last:border-b-0"
              onMouseDown={() => handleSelect(market.conditionId)}
            >
              <RiskBadge level={market.verdict} />
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-body truncate">{market.question}</p>
                <p className="text-muted text-xs font-data">Closes {formatDate(market.resolutionDate)}</p>
              </div>
              {market.direction && market.verdict !== 'clean' && (
                <span
                  className={`text-xs font-mono shrink-0 ${
                    market.direction === 'yes' ? 'text-yes' : 'text-no'
                  }`}
                >
                  {market.direction.toUpperCase()}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </form>
  )
}
