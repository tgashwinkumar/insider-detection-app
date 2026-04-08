const BASE_URL = import.meta.env.VITE_API_URL 

async function fetchJson(path) {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`)
  return res.json()
}

/**
 * Search markets by query string, Polymarket URL, condition ID, or token ID.
 * @param {string} query
 * @returns {Promise<Array>}
 */
export function searchMarkets(query) {
  return fetchJson(`/api/markets/search?q=${encodeURIComponent(query)}`)
}

/**
 * Get all trades for a market, enriched with insider classification.
 * @param {string} conditionId
 * @returns {Promise<Object>} { market, trades, verdict }
 */
export function getMarketTrades(conditionId) {
  return fetchJson(`/api/markets/${conditionId}/trades`)
}

/**
 * Get insider score breakdown for a wallet address.
 * @param {string} address
 * @returns {Promise<Object>} { address, insiderScore, factors, trades }
 */
export function getWalletScore(address) {
  return fetchJson(`/api/wallets/${address}/score`)
}

/**
 * Get live alerts feed (most recently flagged trades across all markets).
 * @returns {Promise<Array>}
 */
export function getAlerts() {
  return fetchJson('/api/alerts')
}

/**
 * Trigger historical ingestion for a market/event.
 * @param {string} query - conditionId, Polymarket URL, or slug
 * @returns {Promise<{totalMarkets: number, jobs: Array}>}
 */
export function startIngest(query) {
  return fetchJson(`/api/ingest?q=${encodeURIComponent(query)}`)
}

/**
 * Poll the current state of an ingestion job for a single market.
 * @param {string} conditionId
 * @returns {Promise<{status, tradesIndexed, walletsFound, batchesProcessed, error, warnings}>}
 */
export function getIngestStatus(conditionId) {
  return fetchJson(`/api/ingest/${conditionId}/status`)
}
