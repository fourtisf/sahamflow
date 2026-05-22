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

export interface StockAnalysis {
  ticker: string;
  last_close: number | null;
  composite_score: number | null;
  signal: string | null;
  indicators: Record<string, number | string> | null;
  bandar: Record<string, unknown> | null;
  foreign_flow: Record<string, unknown> | null;
  narrative: string | null;
}
