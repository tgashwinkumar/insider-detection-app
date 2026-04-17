/**
 * Per-market WebSocket hook.
 *
 * Connects to /ws/market/{conditionId} on the backend when a market page mounts.
 * The backend subscribes to the Polymarket Market Channel for that market's token IDs.
 *
 * Two message types are handled:
 *   trade_pending — a trade was detected on the Polymarket WS but not yet scored.
 *                   Shows a pulsing placeholder row in the trade table.
 *   new_trade     — the trade has been reconciled on-chain and fully scored.
 *                   Replaces the placeholder (or inserts as a new row).
 *
 * Disconnects cleanly on unmount, which triggers the backend to decrement
 * the viewer ref count and unsubscribe from Polymarket WS if no viewers remain.
 */
import { useState, useEffect, useRef, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

export function useMarketWebSocket(conditionId) {
  const [pendingLiveTrades, setPendingLiveTrades] = useState([])
  const [newLiveTrades, setNewLiveTrades] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    if (!conditionId) return
    try {
      const ws = new WebSocket(`${WS_BASE}/market/${conditionId}`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'ping') return

          if (msg.type === 'trade_pending') {
            setPendingLiveTrades((prev) => {
              // Deduplicate by asset_id + timestamp
              const key = `${msg.asset_id}-${msg.timestamp}`
              if (prev.some((p) => `${p.asset_id}-${p.timestamp}` === key)) return prev
              return [msg, ...prev]
            })
          } else if (msg.type === 'new_trade' && msg.trade) {
            const trade = msg.trade
            // Remove the pending placeholder whose asset_id matches this trade's assets.
            // The backend includes makerAssetId and takerAssetId on the new_trade payload.
            setPendingLiveTrades((prev) =>
              prev.filter(
                (p) =>
                  p.asset_id !== trade.makerAssetId &&
                  p.asset_id !== trade.takerAssetId
              )
            )
            // Insert the scored trade (deduplicate by id = tx_hash)
            setNewLiveTrades((prev) => {
              if (prev.some((t) => t.id === trade.id)) return prev
              return [trade, ...prev]
            })
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        setConnected(false)
      }

      ws.onclose = () => {
        setConnected(false)
        // Reconnect after 5s (longer than useWebSocket to avoid hammering)
        reconnectRef.current = setTimeout(connect, 5000)
      }
    } catch {
      // Connection errors are non-fatal; polling in useTradeData is the fallback
    }
  }, [conditionId])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  return { pendingLiveTrades, newLiveTrades, connected }
}
