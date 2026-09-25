import { useCallback, useState } from 'react'

export interface GraphConfig {
  linkDistance: number       // 50–300, default 150
  chargeStrength: number     // −1000…−100, default −400
  collideRadius: number      // 10–40, default 22
  clusterStrength: number    // 0–0.3, default 0 (off — connectivity drives clusters)
  labelShowZoom: number      // 0.3–1.5, default 0.6
}

export const DEFAULT_GRAPH_CONFIG: GraphConfig = {
  linkDistance: 110,
  chargeStrength: -800,
  collideRadius: 40,
  clusterStrength: 0.0,
  labelShowZoom: 0.6,
}

export const GRAPH_CONFIG_STORAGE_KEY = 'graph_viewer_config'

function readStoredConfig(): GraphConfig {
  if (typeof window === 'undefined') return DEFAULT_GRAPH_CONFIG
  try {
    const raw = localStorage.getItem(GRAPH_CONFIG_STORAGE_KEY)
    if (!raw) return DEFAULT_GRAPH_CONFIG
    const parsed = JSON.parse(raw) as Partial<GraphConfig>
    return { ...DEFAULT_GRAPH_CONFIG, ...parsed }
  } catch {
    return DEFAULT_GRAPH_CONFIG
  }
}

export interface UseGraphConfigResult {
  config: GraphConfig
  setConfig: (next: GraphConfig) => void
  resetConfig: () => void
}

export function useGraphConfig(): UseGraphConfigResult {
  const [config, setConfigState] = useState<GraphConfig>(() => readStoredConfig())

  const setConfig = useCallback((next: GraphConfig) => {
    setConfigState(next)
    if (typeof window !== 'undefined') {
      localStorage.setItem(GRAPH_CONFIG_STORAGE_KEY, JSON.stringify(next))
    }
  }, [])

  const resetConfig = useCallback(() => {
    setConfigState(DEFAULT_GRAPH_CONFIG)
    if (typeof window !== 'undefined') {
      localStorage.removeItem(GRAPH_CONFIG_STORAGE_KEY)
    }
  }, [])

  return { config, setConfig, resetConfig }
}
