import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

export function useWebSocket(path = '/trades') {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(`${WS_URL}${path}`)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setLoading(false)
        setError(null)
      }

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data)
          setData(parsed)
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection failed')
        setConnected(false)
      }

      ws.onclose = () => {
        setConnected(false)
        // Reconnect after 3s
        reconnectRef.current = setTimeout(connect, 3000)
      }
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  return { data, loading, error, connected }
}
