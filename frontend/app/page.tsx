"use client";

import { useEffect, useMemo, useState } from "react";
import { IhsgChart, EquityChart } from "@/components/Charts";
import { PortfolioBacktest } from "@/components/PortfolioBacktest";
import { ReversalCandidates } from "@/components/ReversalCandidates";
import { SmartAnalysis } from "@/components/SmartAnalysis";
import { StockSearch } from "@/components/StockSearch";
import { api, type GapRadarResponse, type PnlSummary, type TradeRecord } from "@/lib/api";
import { STOCKS, IHSG_30D, EQUITY, BENCHMARK } from "@/lib/fallback";
import type { RegimeResponse, ScreenerRow } from "@/lib/types";

type View = "all" | "gap" | "pnl" | "bandar" | "screener" | "risk" | "backtest" | "journal";
const TABS: { v: View; label: string }[] = [
  { v: "all", label: "Dashboard" },
  { v: "gap", label: "Gap Radar" },
  { v: "pnl", label: "Live PnL" },
  { v: "bandar", label: "Bandar" },
  { v: "screener", label: "Screener" },
  { v: "risk", label: "Risk" },
  { v: "backtest", label: "Backtest" },
  { v: "journal", label: "Journal" },
];

const PATTERN_LABELS: Record<string, { title: string; emoji: string; subtitle: string }> = {
  GAP_FILL_BULL: { title: "GAP FILL BULLISH", emoji: "💎", subtitle: "REVERSAL — gap down dibayar ke atas" },
  GAP_AND_GO: { title: "GAP & GO", emoji: "🚀", subtitle: "BULLISH continuation dengan follow-through" },
  GAP_UP_FAIL: { title: "GAP UP FAIL", emoji: "⚠️", subtitle: "EXHAUSTION trap — distribusi" },
  GAP_DN_CONT: { title: "GAP DOWN CONTINUATION", emoji: "💀", subtitle: "BEARISH persist — hindari" },
};

type Quote = { value: number; change: number; change_pct: number } | null;

function IndexCell({ label, q, decimals = 2 }: { label: string; q: Quote; decimals?: number }) {
  if (!q) {
    return (
      <div className="ix">
        <span className="ix-l">{label}</span>
        <span className="ix-v mono">—</span>
        <span className="ix-c fl mono">menunggu data</span>
      </div>
    );
  }
  const up = q.change >= 0;
  const sign = up ? "+" : "";
  return (
    <div className="ix">
      <span className="ix-l">{label}</span>
      <span className="ix-v mono">{q.value.toLocaleString("id-ID", { maximumFractionDigits: decimals })}</span>
      <span className={`ix-c ${up ? "up" : "dn"} mono`}>
        {sign}{q.change.toLocaleString("id-ID", { maximumFractionDigits: decimals })} {sign}{q.change_pct}%
      </span>
    </div>
  );
}

const parseNum = (s: string) => parseInt(String(s).replace(/[^0-9]/g, ""), 10) || 0;
const fmtID = (n: number) => Math.round(n).toLocaleString("id-ID");
const fmtJt = (n: number) => (n / 1e6).toFixed(1) + "jt";

function phaseTooltip(phase?: string | null) {
  const p = (phase || "").toLowerCase();
  if (p.startsWith("accum")) return "ACCUMULATION (Wyckoff fase 1): smart money diam-diam beli di harga rendah, harga sideways. Setup awal bullish.";
  if (p.startsWith("markup")) return "MARKUP (Wyckoff fase 2): tren naik aktif, retail mulai sadar. Setup trend-following bullish.";
  if (p.startsWith("distrib")) return "DISTRIBUTION (Wyckoff fase 3): smart money jualan di puncak, harga sideways di atas. Warning bearish.";
  if (p.startsWith("markd")) return "MARKDOWN (Wyckoff fase 4): harga dijatuhkan, smart money sudah keluar. Bearish — atau kapitulasi kalau dekat bottom.";
  return "";
}

function phaseClass(phase?: string | null) {
  const p = (phase || "").toLowerCase();
  if (p.startsWith("markup")) return "ph-mk";
  if (p.startsWith("accum")) return "ph-ac";
  if (p.startsWith("distrib")) return "ph-di";
  if (p.startsWith("markd")) return "ph-md";
  return "ph-ac";
}
function scoreClass(s?: number | null) {
  if (s == null) return "sc-m";
  if (s >= 80) return "sc-h";
  if (s >= 65) return "sc-m";
  return "sc-l";
}

// Bandar score color follows PHASE direction (Markdown high score = strong bearish = red,
// Markup/Accum high score = strong bullish = green) — not raw score level.
function bandarScoreClass(score: number | null | undefined, phase: string | null | undefined) {
  if (score == null) return "fl";
  const p = (phase || "").toLowerCase();
  if (p.startsWith("markup") || p.startsWith("accum")) return score >= 65 ? "up" : "am";
  if (p.startsWith("markd") || p.startsWith("distrib")) return score >= 65 ? "dn" : "am";
  return "fl";
}

export default function Dashboard() {
  const [view, setView] = useState<View>("all");
  const [regime, setRegime] = useState<RegimeResponse | null>(null);
  const [rows, setRows] = useState<ScreenerRow[]>([]);
  const [live, setLive] = useState(false);
  const [indices, setIndices] = useState<Record<string, Quote> | null>(null);
  const [ihsg, setIhsg] = useState<{ closes: number[]; support: number | null; resistance: number | null; last: number | null } | null>(null);

  const [sel, setSel] = useState("BBCA");
  const [modal, setModal] = useState("500.000.000");
  const [entry, setEntry] = useState("9.825");
  const [clock, setClock] = useState("");
  const [gapData, setGapData] = useState<GapRadarResponse | null>(null);
  const [pnlData, setPnlData] = useState<PnlSummary | null>(null);
  const [tradesData, setTradesData] = useState<TradeRecord[] | null>(null);

  // Fetch gap radar / pnl / trades on demand per view
  useEffect(() => {
    if (view === "gap" || view === "all") api.gapRadar().then(setGapData);
    if (view === "pnl" || view === "all") api.pnlSummary().then(setPnlData);
    if (view === "journal") api.tradesList().then(setTradesData);
  }, [view]);

  // Restore last selection from localStorage on mount; default tetap BBCA.
  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("sahamflow:sel") : null;
    if (saved) setSel(saved);
  }, []);

  // Persist selection.
  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("sahamflow:sel", sel);
  }, [sel]);

  useEffect(() => {
    (async () => {
      const [r, s, idx, hist] = await Promise.all([
        api.regimeCurrent(),
        api.screener(-1),
        api.indices(),
        api.ihsgHistory(30),
      ]);
      if (r) setRegime(r);
      if (s && s.length) {
        setRows(s);
        setLive(true);
      }
      if (idx) setIndices(idx);
      if (hist && hist.history?.length) {
        setIhsg({
          closes: hist.history.map((h) => h.close),
          support: hist.support,
          resistance: hist.resistance,
          last: hist.last,
        });
      }
    })();
  }, []);

  useEffect(() => {
    const tick = () => {
      const n = new Date();
      setClock(`${String(n.getHours()).padStart(2, "0")}:${String(n.getMinutes()).padStart(2, "0")}`);
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, []);

  // Position sizer (1% risk, SL ATR×2≈6%, R:R 1:3) — ported from prototype calcSizer.
  const sizer = useMemo(() => {
    const m = parseNum(modal);
    const e = parseNum(entry);
    if (!m || !e) return null;
    const slPct = 0.06, tpPct = 0.18, riskPct = 0.01;
    const sl = e * (1 - slPct);
    const tp = e * (1 + tpPct);
    const riskRupiah = m * riskPct;
    const shares = Math.floor(riskRupiah / (e - sl));
    return {
      sl: `${fmtID(sl)} (-6%)`,
      tp: `${fmtID(tp)} (+18%)`,
      risk: `Rp ${fmtID(riskRupiah)}`,
      pos: `${fmtID(shares)} lbr · Rp ${fmtJt(shares * e)}`,
    };
  }, [modal, entry]);

  const meta = STOCKS[sel] ?? STOCKS.BREN;

  function selectStock(sym: string) {
    setSel(sym.toUpperCase());
    if (STOCKS[sym]) setEntry(fmtID(STOCKS[sym].price));
    // SmartAnalysis will fetch fresh intel for any ticker (lazy-fetch backend).
    document.getElementById("smart-analysis-anchor")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Watchlist sekarang dari screener (45 LQ45) sortir by composite score.
  // STOCKS meta dipakai sebagai overlay opsional untuk saham yang punya meta.
  const watch = useMemo(() => {
    if (rows.length === 0) {
      // Fallback ke STOCKS sampai data screener masuk
      return Object.keys(STOCKS).map((t) => ({ ticker: t, live: null, meta: STOCKS[t] }));
    }
    return rows.map((r) => ({
      ticker: r.ticker,
      live: r,
      meta: STOCKS[r.ticker] ?? null,
    }));
  }, [rows]);

  const fmtPrice = (n: number | null | undefined) => n == null ? "—" : Math.round(n).toLocaleString("id-ID");

  const show = (grp: string) => view === "all" || grp.split(" ").includes(view);

  return (
    <>
      <nav className="nav">
        <div className="navin">
          <div className="brand">
            <img src="/icon.svg" alt="Sahamflow" className="bmark-img" width={34} height={34} />
            <div className="bname"><span className="brand-saham">Saham</span><span className="brand-flow">flow</span></div>
          </div>
          <div className="ntabs">
            {TABS.map((t) => (
              <div key={t.v} className={`ntab${view === t.v ? " on" : ""}`} onClick={() => setView(t.v)}>
                {t.label}
              </div>
            ))}
          </div>
          <StockSearch onSelect={selectStock} />
          <div className="nright">
            <div className="nstat">
              <span className="live" /><span className="hide">{live ? "DATA LIVE" : "IDX EOD"}</span><span>{clock}</span>
            </div>
            <div className="av" title="Account">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="8" r="4" fill="#1a1200"/>
                <path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#1a1200" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
              </svg>
            </div>
          </div>
        </div>
      </nav>

      <div className="wrap">
        <div className="head">
          <div>
            <div className="htitle">Selamat datang di <span className="goldtext">Sahamflow</span></div>
            <div className="hsub">
              {regime?.regime ? `Regime · ${regime.regime}` : "Menunggu data IHSG…"}
              {regime?.modifier ? ` → ${regime.modifier}` : ""}
            </div>
          </div>
          <div className="hact">
            <button className="btn" onClick={() => location.reload()}>⟲ Refresh</button>
            <button className="btn btng">+ Trade Baru</button>
          </div>
        </div>

        {/* INDEX */}
        {show("all") && <div className="pnl sec">
          <div className="idx">
            <IndexCell label="IHSG COMPOSITE" q={indices?.ihsg ?? null} />
            <IndexCell label="LQ45" q={indices?.lq45 ?? null} />
            <IndexCell label="USD/IDR" q={indices?.usdidr ?? null} decimals={0} />
            <div className="ix"><span className="ix-l">SBN 10Y</span><span className="ix-v mono">6.78%</span><span className="ix-c fl mono">MANUAL</span></div>
            <div className="ix"><span className="ix-l">BI RATE</span><span className="ix-v mono">6.00%</span><span className="ix-c fl mono">MANUAL</span></div>
            <div className="ix"><span className="ix-l">SMART MONEY</span><span className="ix-v gd mono">—</span><span className="ix-c fl mono">cek per saham</span></div>
          </div>
        </div>}

        {/* REGIME */}
        {show("all") && <div className="pnl sec">
          <div className="pnl-h"><span className="pnl-t">Market Regime</span><span className="pnl-n">Multi-Factor Model</span><div className="pnl-r"><span className="pdot" />{live ? "LIVE" : "EOD"}</div></div>
          <div className="reg">
            <span className="reg-tag"><span className="d" /><span className="t">{(regime?.regime || "—").toUpperCase()}</span></span>
            {regime?.modifier && (
              <span className="reg-tag" style={{ background: "rgba(255,210,74,0.1)", borderColor: "rgba(255,210,74,0.3)" }}>
                <span className="t" style={{ color: "var(--gold)" }}>→ {regime.modifier.toUpperCase()}</span>
              </span>
            )}
            <span className="reg-txt">
              Breadth <b>{regime?.breadth_ratio != null ? `${regime.breadth_ratio}×` : "—"}</b> ·{" "}
              Skor model <b>{regime?.raw_score ?? "—"}</b>
              {regime?.path_signals?.return_30d_pct != null && (<> · 30D <b>{regime.path_signals.return_30d_pct}%</b></>)}
              {regime?.path_signals?.streak_down != null && regime.path_signals.streak_down > 0 && (<> · Streak Turun <b>{regime.path_signals.streak_down}D</b></>)}
              {regime?.path_signals?.reversal_day && (<> · <b className="gd">Reversal Day +{regime.path_signals.reversal_day.reversal_pct}%</b></>)}
              {regime?.path_signals?.gap_filled_today && (<> · <b className="gd">Gap Closed</b></>)}
            </span>
            <span className="reg-conf">CONFIDENCE <b>{regime?.confidence != null ? `${regime.confidence}%` : "—"}</b></span>
          </div>
          <div className="drv">
            <div className="dc"><div className="dc-l">A/D Ratio</div><div className="dc-v up mono">{regime?.breadth_ratio != null ? `${regime.breadth_ratio}×` : "—"}</div><div className="dc-m">Advance/decline</div></div>
            <div className="dc"><div className="dc-l">Smart Money</div><div className="dc-v gd mono">PROXY</div><div className="dc-m">Per saham di Smart Analysis</div></div>
            <div className="dc"><div className="dc-l">vs MA200</div><div className="dc-v up mono">{regime?.factors?.ma200 != null ? regime.factors.ma200 : "—"}</div><div className="dc-m">Posisi tren</div></div>
            <div className="dc"><div className="dc-l">Raw Score</div><div className="dc-v mono">{regime?.raw_score ?? "—"}</div><div className="dc-m">-1 .. +1</div></div>
          </div>
        </div>}

        {/* BRIEF + CHART */}
        {show("all") && <div className="r2 sec">
          <div className="pnl">
            <div className="pnl-h"><span className="pnl-t">AI Morning Brief</span><span className="pnl-n">Sahamflow Intelligence</span><div className="pnl-r"><span className="pdot" />{clock}</div></div>
            <div className="pnl-b">
              <div className="brief">
                <p>IHSG dalam fase <b>{regime?.regime || "—"}</b> dengan confidence <b>{regime?.confidence ?? "—"}%</b>. Skor multi-faktor saat ini <span className="k">{regime?.raw_score ?? "—"}</span> (rentang -1 sampai +1).</p>
                <p>Breadth A/D <b>{regime?.breadth_ratio ?? "—"}×</b>. Narasi AI penuh tersedia setelah <span className="k">ANTHROPIC_API_KEY</span> aktif dan endpoint <span className="k">/brief/today</span> dipanggil.</p>
                <p>{ihsg?.support != null && ihsg?.resistance != null ? (<>Level kunci IHSG 30D: <span className="k">SUPPORT {ihsg.support.toLocaleString("id-ID")}</span> · <span className="k">RESIST {ihsg.resistance.toLocaleString("id-ID")}</span>. Foreign net masih menunggu data IDX (Tahap 3).</>) : "Foreign flow & support/resistance konkret menyusul setelah scraper IDX (Tahap 3) mengisi data foreign net."}</p>
              </div>
              <div className="bf">
                <div className="bfc"><div className="bfc-l">Bias</div><div className="bfc-v up">▲ {regime && (regime.raw_score ?? 0) > 0 ? "BULLISH" : "NETRAL"}</div></div>
                <div className="bfc"><div className="bfc-l">Confidence</div><div className="bfc-v gd">{regime?.confidence ?? "—"}%</div></div>
                <div className="bfc"><div className="bfc-l">Sumber</div><div className="bfc-v am">{live ? "LIVE" : "EOD"}</div></div>
              </div>
            </div>
          </div>
          <div className="pnl">
            <div className="pnl-h"><span className="pnl-t">IHSG 30D</span><span className="pnl-n">Daily{ihsg ? "" : " · contoh"}</span><div className="pnl-r gd">{ihsg?.last != null ? ihsg.last.toLocaleString("id-ID") : "—"}</div></div>
            <div className="pnl-b"><div className="cw"><IhsgChart data={ihsg?.closes?.length ? ihsg.closes : IHSG_30D} /></div></div>
          </div>
        </div>}

        {/* SMART ANALYSIS — per-stock buy-side intel */}
        {show("all") && <div id="smart-analysis-anchor" />}
        {show("all") && <SmartAnalysis ticker={sel} />}

        {/* GAP RADAR PAGE */}
        {show("gap") && <div className="pnl sec">
          <div className="pnl-h">
            <span className="pnl-t">📊 Gap Radar — IDX LQ45</span>
            <span className="pnl-n">{gapData?.ihsg?.date ? `EOD ${gapData.ihsg.date}` : "loading…"}</span>
            <div className="pnl-r"><span className="pdot" />SMART MONEY PATTERN</div>
          </div>
          <div className="pnl-b">
            {!gapData && <div className="alrt alrt-i">Memuat data gap radar…</div>}
            {gapData && (
              <>
                <div className="alrt alrt-i" style={{ marginBottom: 12 }}>
                  <b>Breadth</b>: {gapData.breadth.bullish}🟢 / {gapData.breadth.bearish}🔴 dari {gapData.breadth.total_scanned} ({gapData.breadth.bullish_pct}% bull / {gapData.breadth.bearish_pct}% bear)
                  → <b>{gapData.breadth.label}</b>
                  {gapData.ihsg && (
                    <span> · IHSG {gapData.ihsg.gap_pct >= 0 ? "+" : ""}{gapData.ihsg.gap_pct}% gap · close {gapData.ihsg.close.toLocaleString("id-ID")} · day {gapData.ihsg.day_change_pct >= 0 ? "🟢+" : "🔴"}{gapData.ihsg.day_change_pct}%</span>
                  )}
                </div>
                {["GAP_FILL_BULL", "GAP_AND_GO", "GAP_UP_FAIL", "GAP_DN_CONT"].map((pat) => {
                  const rows = gapData.groups[pat] || [];
                  if (!rows.length) return null;
                  const meta = PATTERN_LABELS[pat];
                  const stat = gapData.stats[pat];
                  return (
                    <div key={pat} style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 6, fontWeight: 600, color: "var(--gold)" }}>
                        {meta.emoji} {meta.title}
                        {stat?.n ? <span style={{ marginLeft: 8, fontSize: 11, color: "var(--mute)" }}>hist win {stat.win_rate_pct}% (avg {stat.avg_return_pct! >= 0 ? "+" : ""}{stat.avg_return_pct}%, n={stat.n})</span> : null}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--mute)", marginBottom: 6 }}>{meta.subtitle}</div>
                      <table className="dt">
                        <thead><tr><th>Ticker</th><th>Sector</th><th className="r">Gap%</th><th className="r">Day%</th><th className="r">Close</th><th className="r">Vol×</th><th className="r">vs MA200</th><th>Entry Plan</th></tr></thead>
                        <tbody>
                          {rows.map((r) => (
                            <tr key={r.ticker} onClick={() => { setSel(r.ticker); setView("all"); }}>
                              <td><b>{r.ticker}</b></td>
                              <td style={{ fontSize: 11 }}>{r.sector || "—"}</td>
                              <td className={`r mono ${r.gap_pct >= 0 ? "up" : "dn"}`}>{r.gap_pct >= 0 ? "+" : ""}{r.gap_pct}%</td>
                              <td className={`r mono ${r.day_change_pct >= 0 ? "up" : "dn"}`}>{r.day_change_pct >= 0 ? "+" : ""}{r.day_change_pct}%</td>
                              <td className="r mono">{r.close.toLocaleString("id-ID")}</td>
                              <td className="r mono">{r.volume_ratio_20d != null ? `${r.volume_ratio_20d.toFixed(1)}×` : "—"}</td>
                              <td className={`r mono ${(r.ma200_distance_pct ?? 0) >= 0 ? "up" : "dn"}`}>{r.ma200_distance_pct != null ? `${r.ma200_distance_pct >= 0 ? "+" : ""}${r.ma200_distance_pct}%` : "—"}</td>
                              <td style={{ fontSize: 11 }}>{r.entry_plan || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                })}
                <div style={{ fontSize: 11, color: "var(--mute)", marginTop: 8 }}>⚡ Cross-check sebelum entry: volume real-time, foreign flow di RTI/Stockbit, struktur chart.</div>
              </>
            )}
          </div>
        </div>}

        {/* LIVE PnL PAGE */}
        {show("pnl") && <div className="pnl sec">
          <div className="pnl-h">
            <span className="pnl-t">📌 Live Performance</span>
            <span className="pnl-n">Real-time dari Trade table</span>
            <div className="pnl-r"><span className="pdot" />{pnlData ? "LIVE" : "loading"}</div>
          </div>
          <div className="pnl-b">
            {!pnlData && <div className="alrt alrt-i">Memuat data PnL…</div>}
            {pnlData && (
              <>
                <div className="idx" style={{ marginBottom: 12 }}>
                  <div className="ix"><span className="ix-l">TOTAL TRADES</span><span className="ix-v mono">{pnlData.totals.trades}</span><span className="ix-c fl mono">{pnlData.totals.open} open · {pnlData.totals.closed} closed</span></div>
                  <div className="ix"><span className="ix-l">WIN RATE</span><span className="ix-v mono">{pnlData.totals.win_rate_pct}%</span><span className="ix-c fl mono">{pnlData.totals.wins}W / {pnlData.totals.losses}L</span></div>
                  <div className="ix"><span className="ix-l">TOTAL PnL</span><span className={`ix-v mono ${pnlData.totals.total_pnl_pct >= 0 ? "up" : "dn"}`}>{pnlData.totals.total_pnl_pct >= 0 ? "+" : ""}{pnlData.totals.total_pnl_pct}%</span><span className="ix-c fl mono">equal-weight</span></div>
                  <div className="ix"><span className="ix-l">AVG WIN</span><span className="ix-v up mono">+{pnlData.totals.avg_win_pct}%</span><span className="ix-c fl mono">per trade</span></div>
                  <div className="ix"><span className="ix-l">AVG LOSS</span><span className="ix-v dn mono">{pnlData.totals.avg_loss_pct}%</span><span className="ix-c fl mono">per trade</span></div>
                </div>
                {pnlData.open_positions.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 6, fontWeight: 600, color: "var(--gold)" }}>Open Positions ({pnlData.open_positions.length})</div>
                    <table className="dt">
                      <thead><tr><th>Ticker</th><th className="r">Entry</th><th className="r">Last</th><th className="r">Unrealized</th><th className="r">SL</th><th className="r">TP</th><th>Setup</th></tr></thead>
                      <tbody>
                        {pnlData.open_positions.map((p) => (
                          <tr key={p.ticker} onClick={() => { setSel(p.ticker); setView("all"); }}>
                            <td><b>{p.ticker}</b></td>
                            <td className="r mono">{p.entry.toLocaleString("id-ID")}</td>
                            <td className="r mono">{p.last.toLocaleString("id-ID")}</td>
                            <td className={`r mono ${p.unrealized_pct >= 0 ? "up" : "dn"}`}>{p.unrealized_pct >= 0 ? "+" : ""}{p.unrealized_pct}%</td>
                            <td className="r mono">{p.stop_loss?.toLocaleString("id-ID") || "—"}</td>
                            <td className="r mono">{p.take_profit?.toLocaleString("id-ID") || "—"}</td>
                            <td style={{ fontSize: 11 }}>{p.setup || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {pnlData.closed_recent.length > 0 && (
                  <div>
                    <div style={{ marginBottom: 6, fontWeight: 600, color: "var(--gold)" }}>Recent Closed (20)</div>
                    <table className="dt">
                      <thead><tr><th>Ticker</th><th className="r">Entry</th><th className="r">Exit</th><th className="r">PnL %</th><th>Setup</th><th>Closed</th></tr></thead>
                      <tbody>
                        {pnlData.closed_recent.map((c, i) => (
                          <tr key={i}>
                            <td><b>{c.ticker}</b></td>
                            <td className="r mono">{c.entry?.toLocaleString("id-ID") || "—"}</td>
                            <td className="r mono">{c.exit?.toLocaleString("id-ID") || "—"}</td>
                            <td className={`r mono ${c.pnl_pct >= 0 ? "up" : "dn"}`}>{c.pnl_pct >= 0 ? "+" : ""}{c.pnl_pct}%</td>
                            <td style={{ fontSize: 11 }}>{c.setup || "—"}</td>
                            <td style={{ fontSize: 11 }}>{c.exit_date?.slice(0, 10) || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {pnlData.totals.trades === 0 && (
                  <div className="alrt alrt-i">Belum ada trade. Signal masuk dari Telegram bot otomatis akan dicatat di sini.</div>
                )}
              </>
            )}
          </div>
        </div>}

        {/* BANDAR + REVERSAL CANDIDATES */}
        {show("bandar") && (
          <div className="r2e sec">
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Bandar Detection</span><span className="pnl-n">Wyckoff · Estimasi (butuh broker summary untuk presisi)</span><div className="pnl-r"><span className="pdot" />SCAN</div></div>
              <table className="dt">
                <thead><tr><th className="n">#</th><th>Sym</th><th className="r">Last</th><th>Phase</th><th className="r">Score</th></tr></thead>
                <tbody>
                  {watch.map((w, i) => (
                    <tr key={w.ticker} onClick={() => selectStock(w.ticker)}>
                      <td className="n">{i + 1}</td>
                      <td className="sym">{w.ticker}</td>
                      <td className="r mono">{(w.live?.indicators as any)?.last_close ? fmtID((w.live?.indicators as any).last_close) : (w.meta ? fmtID(w.meta.price) : "—")}</td>
                      <td><span className={`ph ${phaseClass(w.live?.bandar_phase)}`} title={phaseTooltip(w.live?.bandar_phase)}>{w.live?.bandar_phase || "—"}</span></td>
                      <td className={`scl ${scoreClass(w.live?.bandar_score)} mono`}>{w.live?.bandar_score ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ReversalCandidates active={regime?.modifier === "Potential Accumulation"} />
          </div>
        )}

        {/* RISK — Portfolio Risk & Position Sizer dihapus per permintaan user.
            Sizing & risk gating sekarang built-in di Smart Analysis (ATR levels +
            quality threshold). Pre-trade check tetap tersedia via API
            POST /api/v1/portfolio/check untuk integrasi otomatis nanti. */}
        {show("risk") && (
          <div className="pnl sec">
            <div className="pnl-h"><span className="pnl-t">Risk</span><span className="pnl-n">Built into Smart Analysis</span></div>
            <div className="pnl-b">
              <div className="alrt alrt-i">
                <b>► RISK & SIZING DIPINDAH KE SMART ANALYSIS</b><br/>
                Klik saham apa pun → panel <b>Smart Analysis</b> sudah menampilkan
                level eksekusi berbasis ATR (Entry / SL / TP / R:R) per saham,
                konteks regime, dan signature reversal kalau ada. Untuk pre-trade
                check (heat, korelasi, sektor), backend tetap menyediakan
                endpoint <code>POST /api/v1/portfolio/check</code>.
              </div>
            </div>
          </div>
        )}

        {/* Fundamental panel dipindahkan ke Smart Analysis (Quality tier dari yfinance live) */}

        {/* BACKTEST */}
        {show("backtest") && <PortfolioBacktest />}
        {show("backtest") && (
          <div className="pnl sec">
            <div className="pnl-h"><span className="pnl-t">Backtest Engine (per-saham)</span><span className="pnl-n">Per-saham · IDX cost 0.6%</span></div>
            <div className="pnl-b">
              <div className="alrt alrt-i"><b>► CARA PAKAI:</b> Backtest live per saham (walk-forward, cost included). Panggil endpoint:</div>
              <pre style={{ background: "var(--bg2)", padding: 12, borderRadius: 8, fontSize: 11, color: "var(--gold)", overflowX: "auto" }}>
GET /api/v1/backtest?ticker=BBCA&min_score=0.3
              </pre>
              <div className="comp" style={{ borderTop: "none", paddingLeft: 0 }}>
                <b>Track record per setup</b> sudah otomatis tampil di panel <b>Smart Analysis · [TICKER]</b> di atas. Klik salah satu saham di tabel Bandar → scroll ke section <b>TRACK RECORD</b> — itu hit rate, expectancy, profit factor dari setup yang aktif sekarang, dihitung walk-forward biaya 0.6% round-trip.
              </div>
              <div className="cw-sm" style={{ opacity: 0.25, marginTop: 8 }}><EquityChart equity={EQUITY} benchmark={BENCHMARK} /></div>
              <div className="comp"><b>CATATAN:</b> Equity curve di atas adalah <b>placeholder visual</b>, BUKAN hasil backtest nyata. Angka backtest nyata muncul saat memanggil endpoint di atas atau membuka Smart Analysis.</div>
            </div>
          </div>
        )}

        {/* JOURNAL — populate via POST /api/v1/trades */}
        {show("journal") && (
          <div className="pnl sec">
            <div className="pnl-h">
              <span className="pnl-t">📓 Trading Journal</span>
              <span className="pnl-n">{tradesData?.length ?? 0} records</span>
              <div className="pnl-r">
                <a href="/api/v1/trades/export.csv" className="btn" style={{ textDecoration: "none" }}>⬇ Export CSV</a>
              </div>
            </div>
            <div className="pnl-b">
              {!tradesData && <div className="alrt alrt-i">Memuat trade history…</div>}
              {tradesData && tradesData.length === 0 && (
                <div className="alrt alrt-i">Belum ada trade. Signal Telegram otomatis akan tercatat di sini.</div>
              )}
              {tradesData && tradesData.length > 0 && (
                <div style={{ overflowX: "auto" }}>
                  <table className="dt">
                    <thead><tr>
                      <th>Ticker</th><th>Entry Date</th><th className="r">Entry</th>
                      <th>Exit Date</th><th className="r">Exit</th>
                      <th className="r">SL</th><th className="r">TP</th>
                      <th className="r">PnL %</th><th>Setup</th><th>Source</th>
                    </tr></thead>
                    <tbody>
                      {tradesData.map((t, i) => {
                        const pnl = t.pnl_pct ?? null;
                        const isOpen = !t.exit_date;
                        return (
                          <tr key={t.id || i} onClick={() => { setSel(t.ticker); setView("all"); }}>
                            <td><b>{t.ticker}</b>{isOpen && <span style={{ marginLeft: 6, fontSize: 10, color: "var(--gold)" }}>OPEN</span>}</td>
                            <td style={{ fontSize: 11 }}>{t.entry_date?.slice(0, 10) || "—"}</td>
                            <td className="r mono">{t.entry_price?.toLocaleString("id-ID") || "—"}</td>
                            <td style={{ fontSize: 11 }}>{t.exit_date?.slice(0, 10) || "—"}</td>
                            <td className="r mono">{t.exit_price?.toLocaleString("id-ID") || "—"}</td>
                            <td className="r mono">{t.stop_loss?.toLocaleString("id-ID") || "—"}</td>
                            <td className="r mono">{t.take_profit?.toLocaleString("id-ID") || "—"}</td>
                            <td className={`r mono ${pnl != null ? (pnl >= 0 ? "up" : "dn") : ""}`}>{pnl != null ? `${pnl >= 0 ? "+" : ""}${pnl}%` : "—"}</td>
                            <td style={{ fontSize: 11 }}>{t.setup || "—"}</td>
                            <td style={{ fontSize: 11 }}>{t.source || "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* WATCHLIST / SCREENER */}
        {show("screener") && (
          <div className="pnl sec">
            <div className="pnl-h"><span className="pnl-t">Signal Watchlist</span><span className="pnl-n">Composite · {watch.length} Stocks</span><div className="pnl-r gd">{clock} WIB</div></div>
            <div style={{ overflowX: "auto" }}>
              <table className="dt">
                <thead><tr><th className="n">#</th><th>Sym</th><th className="r">Last</th><th className="r">Score</th><th className="r">Bndr</th><th>Phase</th><th className="r">SmartMoney</th><th className="r">Qlty</th><th>Signal</th></tr></thead>
                <tbody>
                  {watch.map((w, i) => (
                    <tr key={w.ticker} onClick={() => selectStock(w.ticker)}>
                      <td className="n">{i + 1}</td>
                      <td className="sym">{w.ticker}</td>
                      <td className="r mono">{(w.live?.indicators as any)?.last_close ? fmtID((w.live?.indicators as any).last_close) : (w.meta ? fmtID(w.meta.price) : "—")}</td>
                      <td className={`r mono ${(w.live?.composite_score ?? 0) >= 0 ? "up" : "dn"}`}>{w.live?.composite_score ?? "—"}</td>
                      <td className={`r mono ${bandarScoreClass(w.live?.bandar_score, w.live?.bandar_phase)}`}>{w.live?.bandar_score ?? "—"}</td>
                      <td><span className={`ph ${phaseClass(w.live?.bandar_phase)}`} title={phaseTooltip(w.live?.bandar_phase)}>{w.live?.bandar_phase || "—"}</span></td>
                      <td className={`r mono ${((w.live?.indicators as any)?.smart_money_score ?? 0) >= 20 ? "up" : ((w.live?.indicators as any)?.smart_money_score ?? 0) <= -20 ? "dn" : "fl"}`}>{(w.live?.indicators as any)?.smart_money_score ?? "—"}</td>
                      <td className="r mono">{((w.live?.indicators as any)?.quality_score ?? w.meta?.qlty) ?? "—"}</td>
                      <td><span className={`sg ${(w.live?.composite_score ?? 0) >= 0.2 ? "sg-b" : (w.live?.composite_score ?? 0) <= -0.2 ? "sg-s" : "sg-h"}`}>{w.live?.signal || "—"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="comp"><b>DISCLOSURE:</b> Sahamflow adalah alat analisis data, BUKAN rekomendasi investasi. Tidak terdaftar di OJK. Pengguna bertanggung jawab penuh atas keputusan. Trading saham berisiko kehilangan modal. Past performance ≠ future results. DYOR.</div>
          </div>
        )}
      </div>
    </>
  );
}
