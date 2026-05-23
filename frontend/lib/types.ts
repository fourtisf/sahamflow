export interface RegimeResponse {
  date: string;
  regime: string | null;
  confidence: number | null;
  raw_score: number | null;
  breadth_ratio: number | null;
  foreign_flow_5d: number | null;
  factors: Record<string, number> | null;
  modifier: string | null;
  path_signals: {
    return_30d_pct?: number;
    return_90d_pct?: number;
    streak_down?: number;
    reversal_day?: { streak_length: number; reversal_pct: number } | null;
    gap_filled_today?: { gap_date: string; gap_top: number; gap_bottom: number } | null;
  } | null;
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
  action: "BUY" | "WATCH" | "AVOID / EXIT" | string;
  bias: "long" | "avoid" | "neutral" | string;
  market_mode: string;
  wait_conditions: string[] | null;
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
  triggers: {
    trigger: Record<string, number | string>;
    invalidation: { level: number; rule: string };
    time_stop_bars: number;
    rules: string[];
  } | null;
  track_record: {
    setup: string;
    n: number;
    hit_rate_pct: number;
    avg_win_pct: number;
    avg_loss_pct: number;
    expectancy_pct: number;
    profit_factor: number;
  } | null;
  history: { date: string; close: number }[];
  alternate_setup: {
    bias: "long" | "short";
    rationale: string;
    reversal_score: number;
    signatures: string[];
    range_position_pct?: number;
    swing_low_60d?: number;
    swing_high_60d?: number;
    levels: {
      entry: number;
      stop_loss: number;
      take_profit: number;
      risk_pct: number;
      reward_pct: number;
      rr_ratio: number;
      tp_clamped_at_structure?: boolean;
    } | null;
    rules: string[];
  } | null;
  structural_warning?: string;
}

export interface PortfolioRisk {
  account_size_idr: number;
  open_positions: number;
  total_value_idr: number;
  total_risk_idr: number;
  portfolio_heat_pct: number;
  heat_limit_pct: number;
  sector_concentration_pct: Record<string, number>;
  sector_limit_pct: number;
  max_correlation: number | null;
  max_correlation_pair: [string, string] | null;
  correlation_limit: number;
  positions: { ticker: string; value_idr: number; risk_idr: number; sector: string | null }[];
}
