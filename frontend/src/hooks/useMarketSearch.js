import { useState, useEffect, useRef } from 'react'
import { searchMarkets } from '../services/api'
import { POLYMARKET_URL_REGEX, CONDITION_ID_REGEX, TOKEN_ID_REGEX } from '../utils/constants'

function detectQueryType(query) {
  if (POLYMARKET_URL_REGEX.test(query)) return 'url'
  if (CONDITION_ID_REGEX.test(query)) return 'conditionId'
  if (TOKEN_ID_REGEX.test(query)) return 'tokenId'
  return 'text'
}

export function useMarketSearch() {
  const [query, setQuery] = useState('')
  const [queryType, setQueryType] = useState('text')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const debounceRef = useRef(null)

  useEffect(() => {
    const type = detectQueryType(query)
    setQueryType(type)

    if (!query.trim()) {
      setResults([])
      return
    }

    // For non-text types, don't show dropdown suggestions
    if (type !== 'text') {
      setResults([])
      return
    }

    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await searchMarkets(query)
        setResults(data.slice(0, 6))
      } catch (err) {
        setError(err.message)
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => clearTimeout(debounceRef.current)
  }, [query])

  return { query, setQuery, queryType, results, loading, error }
}
