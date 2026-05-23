export interface RegimeResponse {
  date: string;
  regime: string | null;
  confidence: number | null;
  raw_score: number | null;
  breadth_ratio: number | null;
  foreign_flow_5d: number | null;
  factors: Record<string, number> | null;
}

export interface ScreenerRow {
  ticker: string;
  composite_score: number | null;
  signal: string | null;
  bandar_phase: string | null;
  bandar_score: number | null;
  foreign_signal: string | null;
  indicators: Record<string, number | string> | null;
}

export interface StockIntel {
  ticker: string;
  last_close: number;
  composite_score: number;
  signal: string;
  indicators: {
    rsi14: number;
    macd_hist: number;
    macd_bias: "bullish" | "bearish";
    stoch_rsi: number;
    ma20: number | null;
    ma50: number | null;
    ma200: number | null;
    ma200_distance_pct: number | null;
    volume_ratio_20d: number | null;
    atr14: number | null;
    atr_pct: number | null;
  };
  bandar: { phase: string; score: number; vol_ratio?: number; estimated: boolean };
  foreign_flow: { has_data: boolean; signal?: string; net_window?: number; consistency?: number };
  levels: {
    entry: number;
    stop_loss: number;
    take_profit: number;
    risk_pct: number;
    reward_pct: number;
    rr_ratio: number;
  } | null;
  regime: {
    name: string | null;
    bias: "long" | "short" | "neutral";
    regime_aligned: boolean;
    conviction_pct: number;
    note: string;
  };
}
