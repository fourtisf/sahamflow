import type { PortfolioRisk, RegimeResponse, ScreenerRow, StockIntel } from "./types";

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
  portfolioRisk: () => get<PortfolioRisk>("/portfolio/risk"),
  health: () => get<{ status: string }>("/../health"),
  gapRadar: () => get<GapRadarResponse>("/gap/radar"),
  pnlSummary: () => get<PnlSummary>("/pnl/summary"),
  tradesList: () => get<TradeRecord[]>("/trades"),
};

export interface GapRadarRow {
  ticker: string;
  pattern: string;
  sector?: string;
  gap_pct: number;
  day_change_pct: number;
  open: number;
  close: number;
  high: number;
  low: number;
  volume_ratio_20d: number | null;
  ma200_distance_pct: number | null;
  entry_plan: string | null;
}
export interface GapRadarResponse {
  ihsg: { gap_pct: number; severity: string; direction: string; close: number; day_change_pct: number; date: string } | null;
  groups: Record<string, GapRadarRow[]>;
  stats: Record<string, { n: number; win_rate_pct: number | null; avg_return_pct: number | null }>;
  breadth: { total_scanned: number; bullish: number; bearish: number; bullish_pct: number; bearish_pct: number; label: string };
}
export interface PnlSummary {
  totals: {
    trades: number; open: number; closed: number; wins: number; losses: number;
    win_rate_pct: number; total_pnl_pct: number; avg_win_pct: number; avg_loss_pct: number;
  };
  open_positions: { ticker: string; entry: number; last: number; unrealized_pct: number; setup: string | null; stop_loss: number | null; take_profit: number | null; entry_date: string | null }[];
  closed_recent: { ticker: string; entry: number | null; exit: number | null; pnl_pct: number; setup: string | null; exit_date: string | null }[];
  equity_curve: { date: string | null; cumulative_pct: number }[];
}
export interface TradeRecord {
  id?: string;
  ticker: string;
  entry_price?: number | null;
  exit_price?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  pnl_pct?: number | null;
  entry_date?: string | null;
  exit_date?: string | null;
  setup?: string | null;
  source?: string | null;
}
