"use client";

import { useEffect, useState } from "react";

import { IhsgChart } from "@/components/Charts";
import { api } from "@/lib/api";
import type { StockIntel } from "@/lib/types";

const fmt = (n: number | null | undefined, d = 2) =>
  n == null ? "—" : n.toLocaleString("id-ID", { maximumFractionDigits: d });

function Bar({ value, min = -1, max = 1, color = "var(--gold)" }: { value: number; min?: number; max?: number; color?: string }) {
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  return (
    <div style={{ height: 4, background: "var(--bg)", borderRadius: 2, overflow: "hidden", marginTop: 4 }}>
      <div style={{ height: "100%", width: `${pct}%`, background: color }} />
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rgc">
      <div className="rg-l">{label}</div>
      <div className="rg-v mono" style={{ fontSize: 15 }}>{value}</div>
      {hint && <div className="rg-m">{hint}</div>}
    </div>
  );
}

export function SmartAnalysis({ ticker }: { ticker: string }) {
  const [intel, setIntel] = useState<StockIntel | null>(null);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [narrLoading, setNarrLoading] = useState(false);
  const [narrError, setNarrError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setIntel(null);
    setNarrative(null);
    setNarrError(null);
    api.stockAnalysis(ticker).then((d) => alive && d && setIntel(d));
    return () => {
      alive = false;
    };
  }, [ticker]);

  async function loadNarrative() {
    setNarrLoading(true);
    setNarrError(null);
    const res = await api.stockNarrative(ticker);
    if (res?.narrative) setNarrative(res.narrative);
    else setNarrError("Narasi tidak tersedia (ANTHROPIC_API_KEY belum aktif di server).");
    setNarrLoading(false);
  }

  if (!intel) {
    return (
      <div className="pnl sec">
        <div className="pnl-h"><span className="pnl-t">Smart Analysis · {ticker}</span><span className="pnl-n">Loading...</span></div>
        <div className="pnl-b" style={{ color: "var(--tx3)" }}>Menarik data dari backend…</div>
      </div>
    );
  }

  const i = intel.indicators;
  const r = intel.regime;
  const lv = intel.levels;
  const sigColor = intel.composite_score >= 0.2 ? "var(--grn)" : intel.composite_score <= -0.2 ? "var(--red)" : "var(--amb)";

  return (
    <div className="pnl sec">
      <div className="pnl-h">
        <span className="pnl-t">Smart Analysis · {ticker}</span>
        <span className="pnl-n">Buy-side intel</span>
        <div className="pnl-r"><span className="pdot" />LIVE</div>
      </div>

      {/* Headline row */}
      <div className="rg" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
        <Stat label="Signal" value={<span style={{ color: sigColor }}>{intel.signal}</span>} hint={`score ${fmt(intel.composite_score, 3)}`} />
        <Stat label="Conviction" value={`${r.conviction_pct}%`} hint={r.regime_aligned ? "selaras regime" : "counter-trend"} />
        <Stat label="Regime" value={r.name ?? "—"} hint={`bias: ${r.bias}`} />
        <Stat label="Bandar" value={intel.bandar.phase} hint={`vol× ${fmt(intel.bandar.vol_ratio ?? null, 2)} · estimasi`} />
      </div>

      {/* Inline price chart 60D */}
      {intel.history && intel.history.length > 0 && (
        <div className="pnl-b" style={{ borderTop: "1px solid var(--line)", padding: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              {ticker} 60D DAILY
            </span>
            <span className="mono gd" style={{ fontSize: 13 }}>{intel.last_close.toLocaleString("id-ID")}</span>
          </div>
          <div className="cw"><IhsgChart data={intel.history.map((h) => h.close)} /></div>
        </div>
      )}

      {/* Indicator breakdown — the numbers a trader actually reads */}
      <div className="pnl-b" style={{ borderTop: "1px solid var(--line)" }}>
        <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
          INDIKATOR — komposisi sinyal
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
          <div>
            <div className="szr"><span className="szl">RSI 14</span><span className="szv mono">{fmt(i.rsi14)}</span></div>
            <Bar value={i.rsi14} min={0} max={100} color={i.rsi14 < 30 ? "var(--grn)" : i.rsi14 > 70 ? "var(--red)" : "var(--gold)"} />
            <div className="rg-m">{i.rsi14 < 30 ? "oversold" : i.rsi14 > 70 ? "overbought" : "netral"}</div>
          </div>
          <div>
            <div className="szr"><span className="szl">MACD Hist</span><span className="szv mono" style={{ color: i.macd_bias === "bullish" ? "var(--grn)" : "var(--red)" }}>{fmt(i.macd_hist, 4)}</span></div>
            <div className="rg-m">{i.macd_bias}</div>
          </div>
          <div>
            <div className="szr"><span className="szl">vs MA200</span><span className="szv mono" style={{ color: (i.ma200_distance_pct ?? 0) >= 0 ? "var(--grn)" : "var(--red)" }}>{fmt(i.ma200_distance_pct)}%</span></div>
            <div className="rg-m">MA200 {fmt(i.ma200)}</div>
          </div>
          <div>
            <div className="szr"><span className="szl">Volume ×20D</span><span className="szv mono">{fmt(i.volume_ratio_20d, 2)}×</span></div>
            <div className="rg-m">{(i.volume_ratio_20d ?? 1) >= 1.5 ? "thrust" : (i.volume_ratio_20d ?? 1) < 0.7 ? "kering" : "normal"}</div>
          </div>
          <div>
            <div className="szr"><span className="szl">Stoch RSI</span><span className="szv mono">{fmt(i.stoch_rsi, 2)}</span></div>
          </div>
          <div>
            <div className="szr"><span className="szl">ATR 14 · %</span><span className="szv mono">{fmt(i.atr14)} · {fmt(i.atr_pct)}%</span></div>
            <div className="rg-m">volatilitas harian</div>
          </div>
        </div>

        {/* Execution levels — ATR-based, per stock */}
        {lv && (
          <>
            <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "14px 0 8px" }}>
              LEVEL EKSEKUSI — berbasis ATR (SL = entry ± 2×ATR, R:R 1:3)
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 1, background: "var(--line)" }}>
              <div className="rgc"><div className="rg-l">Entry (last)</div><div className="rg-v mono">{fmt(lv.entry)}</div></div>
              <div className="rgc"><div className="rg-l">Stop Loss</div><div className="rg-v mono dn">{fmt(lv.stop_loss)}</div><div className="rg-m">risiko {fmt(lv.risk_pct)}%</div></div>
              <div className="rgc"><div className="rg-l">Take Profit</div><div className="rg-v mono up">{fmt(lv.take_profit)}</div><div className="rg-m">reward {fmt(lv.reward_pct)}%</div></div>
              <div className="rgc"><div className="rg-l">R:R</div><div className="rg-v mono gd">1 : {lv.rr_ratio}</div></div>
            </div>
          </>
        )}

        {/* Execution triggers — when to act, when to abandon */}
        {intel.triggers && (
          <>
            <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "14px 0 8px" }}>
              EKSEKUSI — kapan masuk, kapan batal
            </div>
            <div className="rg" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))" }}>
              {Object.entries(intel.triggers.trigger).map(([k, v]) => (
                <div className="rgc" key={k}>
                  <div className="rg-l">{k.replace(/_/g, " ")}</div>
                  <div className="rg-v mono" style={{ fontSize: 13 }}>{String(v)}</div>
                </div>
              ))}
              <div className="rgc">
                <div className="rg-l">invalidation</div>
                <div className="rg-v mono dn" style={{ fontSize: 13 }}>{fmt(intel.triggers.invalidation.level)}</div>
                <div className="rg-m">setup batal di level ini</div>
              </div>
              <div className="rgc">
                <div className="rg-l">time stop</div>
                <div className="rg-v mono" style={{ fontSize: 13 }}>{intel.triggers.time_stop_bars} bar</div>
                <div className="rg-m">keluar jika diam</div>
              </div>
            </div>
            <ul style={{ marginTop: 8, paddingLeft: 18, color: "var(--tx2)", fontSize: 11, lineHeight: 1.7 }}>
              {intel.triggers.rules.map((rule, i) => <li key={i}>{rule}</li>)}
            </ul>
          </>
        )}

        {/* Track record of this setup historically */}
        {intel.track_record && intel.track_record.n > 0 && (
          <>
            <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "14px 0 8px" }}>
              TRACK RECORD — setup ini di {ticker} (walk-forward, biaya IDX 0.6% RT)
            </div>
            <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 6 }}>Setup: <b className="gd">{intel.track_record.setup}</b></div>
            <div className="rg" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(120px,1fr))" }}>
              <Stat label="Sample" value={`${intel.track_record.n} trades`} />
              <Stat label="Hit Rate" value={`${intel.track_record.hit_rate_pct}%`} hint={intel.track_record.hit_rate_pct >= 55 ? "edge positif" : intel.track_record.hit_rate_pct >= 45 ? "marginal" : "negatif"} />
              <Stat label="Avg Win" value={<span className="up">{fmt(intel.track_record.avg_win_pct)}%</span>} />
              <Stat label="Avg Loss" value={<span className="dn">{fmt(intel.track_record.avg_loss_pct)}%</span>} />
              <Stat label="Expectancy" value={<span style={{ color: intel.track_record.expectancy_pct > 0 ? "var(--grn)" : "var(--red)" }}>{fmt(intel.track_record.expectancy_pct)}%</span>} hint="per trade" />
              <Stat label="Profit Factor" value={fmt(intel.track_record.profit_factor)} />
            </div>
          </>
        )}

        {/* Structural warning when Sell signal conflicts with proven support */}
        {intel.structural_warning && (
          <div className="alrt alrt-w" style={{ marginTop: 12 }}>
            <b>⚠ STRUCTURAL WARNING:</b> {intel.structural_warning}
          </div>
        )}

        {/* Alternate setup overlay — smart money flip at bottoms */}
        {intel.alternate_setup && (
          <div
            style={{
              marginTop: 14,
              padding: 12,
              border: "1px solid var(--grn)",
              borderRadius: 8,
              background: "rgba(34,224,122,0.06)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--grn)", letterSpacing: "0.04em" }}>
                ⚠ ALTERNATE SETUP — REVERSAL LONG (override Sell)
              </span>
              <span className="mono" style={{ fontSize: 12, color: "var(--grn)" }}>
                reversal score {intel.alternate_setup.reversal_score}/100
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--tx2)", marginBottom: 8 }}>
              {intel.alternate_setup.rationale}
            </div>
            {intel.alternate_setup.signatures.length > 0 && (
              <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 10 }}>
                <b style={{ color: "var(--gold)" }}>Signature:</b> {intel.alternate_setup.signatures.join(" · ")}
              </div>
            )}
            {intel.alternate_setup.levels && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 1, background: "var(--line)", marginBottom: 10 }}>
                <div className="rgc"><div className="rg-l">Entry (last)</div><div className="rg-v mono">{fmt(intel.alternate_setup.levels.entry)}</div></div>
                <div className="rgc"><div className="rg-l">Stop Loss</div><div className="rg-v mono dn">{fmt(intel.alternate_setup.levels.stop_loss)}</div><div className="rg-m">−{fmt(intel.alternate_setup.levels.risk_pct)}%</div></div>
                <div className="rgc"><div className="rg-l">Take Profit</div><div className="rg-v mono up">{fmt(intel.alternate_setup.levels.take_profit)}</div><div className="rg-m">+{fmt(intel.alternate_setup.levels.reward_pct)}%</div></div>
                <div className="rgc"><div className="rg-l">R:R</div><div className="rg-v mono gd">1 : {intel.alternate_setup.levels.rr_ratio}</div></div>
              </div>
            )}
            <ul style={{ paddingLeft: 18, color: "var(--tx2)", fontSize: 11, lineHeight: 1.7, margin: 0 }}>
              {intel.alternate_setup.rules.map((rule, i) => <li key={i}>{rule}</li>)}
            </ul>
          </div>
        )}

        {/* Regime conviction note */}
        {r.note && (
          <div className="alrt alrt-i" style={{ marginTop: 12 }}>
            <b>► KONTEKS:</b> {r.note}.
          </div>
        )}

        {/* AI narrative on demand */}
        <div style={{ marginTop: 14 }}>
          {narrative ? (
            <div className="brief">
              {narrative.split(/\n\n+/).map((p, idx) => <p key={idx}>{p}</p>)}
            </div>
          ) : (
            <button className="btn btng" onClick={loadNarrative} disabled={narrLoading}>
              {narrLoading ? "Menulis…" : "🧠 Generate AI Narrative (buy-side)"}
            </button>
          )}
          {narrError && <div className="alrt alrt-w" style={{ marginTop: 8 }}><b>⚠</b> {narrError}</div>}
        </div>
      </div>
    </div>
  );
}
