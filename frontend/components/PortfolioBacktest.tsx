"use client";

import { useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

type Result = {
  starting_equity: number;
  final_equity: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  trades: number;
  hit_rate_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  expectancy_pct: number;
  profit_factor: number;
  universe_size: number;
  max_positions: number;
  min_score: number;
  equity_curve: { date: string; equity: number; drawdown_pct: number }[];
  sample_trades: { ticker: string; entry_date: string; exit_date: string; entry: number; exit: number; pnl_pct: number; reason: string }[];
};

const fmtIDR = (n: number) => "Rp " + (n / 1e6).toFixed(1) + " jt";

export function PortfolioBacktest() {
  const [res, setRes] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [params, setParams] = useState({ lookback_days: 500, max_positions: 5, min_score: 0.5 });

  async function run() {
    setLoading(true);
    setRes(null);
    try {
      const r = await fetch(
        `${BASE}/backtest/portfolio?lookback_days=${params.lookback_days}&max_positions=${params.max_positions}&min_score=${params.min_score}`,
        { cache: "no-store" }
      );
      if (r.ok) setRes(await r.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="pnl sec">
      <div className="pnl-h">
        <span className="pnl-t">Portfolio Backtest</span>
        <span className="pnl-n">Walk-forward · long-only · biaya 0.6% RT · sizing 1% risk</span>
      </div>
      <div className="pnl-b">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 12 }}>
          <div>
            <div className="rg-l">Lookback (hari)</div>
            <input className="szi" type="number" value={params.lookback_days} onChange={(e) => setParams({ ...params, lookback_days: +e.target.value })} />
          </div>
          <div>
            <div className="rg-l">Max paralel posisi</div>
            <input className="szi" type="number" value={params.max_positions} onChange={(e) => setParams({ ...params, max_positions: +e.target.value })} />
          </div>
          <div>
            <div className="rg-l">Min score Buy</div>
            <input className="szi" type="number" step="0.05" value={params.min_score} onChange={(e) => setParams({ ...params, min_score: +e.target.value })} />
          </div>
          <button className="btn btng" onClick={run} disabled={loading} style={{ height: 30 }}>
            {loading ? "Menghitung… (bisa 30-60 detik)" : "Run Backtest"}
          </button>
        </div>

        {!res && !loading && (
          <div className="alrt alrt-i">
            <b>► Inilah proof-of-edge.</b> Click "Run Backtest" untuk simulasi: ikuti semua sinyal Sahamflow di seluruh universe LQ45 selama X hari kebelakang, hitung equity curve, drawdown, hit rate, expectancy. Inilah jawaban "tool ini bisa cuan atau tidak".
          </div>
        )}

        {res && (
          <>
            <div className="rg" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))" }}>
              <div className="rgc"><div className="rg-l">Total Return</div><div className={`rg-v mono ${res.total_return_pct >= 0 ? "up" : "dn"}`}>{res.total_return_pct >= 0 ? "+" : ""}{res.total_return_pct}%</div><div className="rg-m">{fmtIDR(res.starting_equity)} → {fmtIDR(res.final_equity)}</div></div>
              <div className="rgc"><div className="rg-l">Max DD</div><div className="rg-v dn mono">{res.max_drawdown_pct}%</div></div>
              <div className="rgc"><div className="rg-l">Trades</div><div className="rg-v mono">{res.trades}</div><div className="rg-m">universe {res.universe_size}</div></div>
              <div className="rgc"><div className="rg-l">Hit Rate</div><div className={`rg-v mono ${res.hit_rate_pct >= 50 ? "up" : "dn"}`}>{res.hit_rate_pct}%</div></div>
              <div className="rgc"><div className="rg-l">Avg Win</div><div className="rg-v up mono">+{res.avg_win_pct}%</div></div>
              <div className="rgc"><div className="rg-l">Avg Loss</div><div className="rg-v dn mono">{res.avg_loss_pct}%</div></div>
              <div className="rgc"><div className="rg-l">Expectancy</div><div className={`rg-v mono ${res.expectancy_pct > 0 ? "up" : "dn"}`}>{res.expectancy_pct > 0 ? "+" : ""}{res.expectancy_pct}%</div><div className="rg-m">per trade</div></div>
              <div className="rgc"><div className="rg-l">Profit Factor</div><div className={`rg-v mono ${res.profit_factor >= 1.5 ? "up" : res.profit_factor >= 1 ? "am" : "dn"}`}>{res.profit_factor}</div></div>
            </div>

            <div style={{ marginTop: 16 }}>
              <div className="rg-l" style={{ marginBottom: 6 }}>SAMPEL TRADE TERAKHIR (max 20)</div>
              <div style={{ maxHeight: 260, overflowY: "auto" }}>
                <table className="dt">
                  <thead><tr><th>Ticker</th><th>Entry</th><th>Exit</th><th className="r">In</th><th className="r">Out</th><th className="r">P&L</th><th>Reason</th></tr></thead>
                  <tbody>
                    {res.sample_trades.map((t, i) => (
                      <tr key={i}>
                        <td className="sym">{t.ticker}</td>
                        <td className="mono fl" style={{ fontSize: 10 }}>{t.entry_date}</td>
                        <td className="mono fl" style={{ fontSize: 10 }}>{t.exit_date}</td>
                        <td className="r mono">{t.entry}</td>
                        <td className="r mono">{t.exit}</td>
                        <td className={`r mono ${t.pnl_pct >= 0 ? "up" : "dn"}`}>{t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct}%</td>
                        <td><span className={`ph ${t.reason === "TP" ? "ph-mk" : t.reason === "SL" ? "ph-md" : "ph-di"}`}>{t.reason}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="comp" style={{ marginTop: 12 }}>
              <b>JUJUR:</b> Backtest ini long-only IDX, biaya 0.6% round-trip, sizing 1% risk. {res.trades} trade tereksekusi dengan threshold score ≥ {res.min_score} dan max {res.max_positions} posisi paralel. Past performance ≠ future results.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
