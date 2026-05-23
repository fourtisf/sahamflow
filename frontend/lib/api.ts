import type { RegimeResponse, ScreenerRow, StockIntel } from "./types";

// Default to a relative path so the same build works behind Nginx (which proxies
// /api -> backend:8000). Override with NEXT_PUBLIC_API_URL for local dev.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const api = {
  regimeCurrent: () => get<RegimeResponse>("/regime/current"),
  screener: (minScore = -1) => get<ScreenerRow[]>(`/screener?min_score=${minScore}`),
  stockAnalysis: (ticker: string) => get<StockIntel>(`/stock/${ticker}/analysis`),
  stockNarrative: (ticker: string) =>
    get<{ ticker: string; intel: StockIntel; narrative: string }>(`/stock/${ticker}/narrative`),
  indices: () =>
    get<Record<string, { value: number; change: number; change_pct: number } | null>>(
      "/market/indices"
    ),
  ihsgHistory: (days = 30) =>
    get<{ history: { date: string; close: number }[]; support: number | null; resistance: number | null; last: number | null }>(
      `/market/ihsg-history?days=${days}`
    ),
  sectorRotation: () =>
    get<{ sector: string; rs_5d_pct: number; constituents: number }[]>("/sectors/rotation"),
  briefToday: () => get<{ brief: string; market_data: Record<string, unknown> }>("/brief/today"),
  health: () => get<{ status: string }>("/../health"),
};
