"use client";

import { useEffect, useMemo, useState } from "react";
import { IhsgChart, EquityChart } from "@/components/Charts";
import { PortfolioBacktest } from "@/components/PortfolioBacktest";
import { ReversalCandidates } from "@/components/ReversalCandidates";
import { SmartAnalysis } from "@/components/SmartAnalysis";
import { StockSearch } from "@/components/StockSearch";
import { api } from "@/lib/api";
import { STOCKS, IHSG_30D, EQUITY, BENCHMARK } from "@/lib/fallback";
import type { RegimeResponse, ScreenerRow } from "@/lib/types";

type View = "all" | "bandar" | "screener" | "risk" | "backtest" | "journal";
const TABS: { v: View; label: string }[] = [
  { v: "all", label: "Dashboard" },
  { v: "bandar", label: "Bandar" },
  { v: "screener", label: "Screener" },
  { v: "risk", label: "Risk" },
  { v: "backtest", label: "Backtest" },
  { v: "journal", label: "Journal" },
];

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
              {regime?.regime ? `Regime: ${regime.regime}` : "IHSG"} ·{" "}
              {live ? "Data sinyal terkini dari backend" : "Menunggu sinkronisasi data backend"}
            </div>
          </div>
          <div className="hact">
            <button className="btn" onClick={() => location.reload()}>⟲ Refresh</button>
            <button className="btn btng">+ Trade Baru</button>
          </div>
        </div>

        {/* INDEX */}
        <div className="pnl sec">
          <div className="idx">
            <IndexCell label="IHSG COMPOSITE" q={indices?.ihsg ?? null} />
            <IndexCell label="LQ45" q={indices?.lq45 ?? null} />
            <IndexCell label="USD/IDR" q={indices?.usdidr ?? null} decimals={0} />
            <div className="ix"><span className="ix-l">SBN 10Y</span><span className="ix-v mono">6.78%</span><span className="ix-c fl mono">MANUAL</span></div>
            <div className="ix"><span className="ix-l">BI RATE</span><span className="ix-v mono">6.00%</span><span className="ix-c fl mono">MANUAL</span></div>
            <div className="ix"><span className="ix-l">SMART MONEY</span><span className="ix-v gd mono">—</span><span className="ix-c fl mono">cek per saham</span></div>
          </div>
        </div>

        {/* REGIME */}
        <div className="pnl sec">
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
        </div>

        {/* BRIEF + CHART */}
        <div className="r2 sec">
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
        </div>

        {/* SMART ANALYSIS — per-stock buy-side intel */}
        <div id="smart-analysis-anchor" />
        <SmartAnalysis ticker={sel} />

        {/* BANDAR + REVERSAL CANDIDATES */}
        {show("bandar screener") && (
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
            <div className="pnl-h"><span className="pnl-t">Trading Journal · Atribusi P&L</span><span className="pnl-n">Endpoint /api/v1/trades & /trades/attribution</span></div>
            <div className="pnl-b">
              <div className="alrt alrt-i"><b>► BELUM ADA TRADE:</b> Catat trade pertama via:
                <pre style={{ background: "var(--bg2)", padding: 10, borderRadius: 6, fontSize: 10.5, color: "var(--gold)", marginTop: 8, overflowX: "auto" }}>
{`curl -X POST https://sahamflow.com/api/v1/trades -H "Content-Type: application/json" \\
  -d '{"ticker":"BBCA","entry_price":5900,"exit_price":6200,"shares":1000,"source":"sahamflow"}'`}
                </pre>
                Setelah ada trade, panel ini otomatis menampilkan jurnal & atribusi P&L (sinyal Sahamflow vs diskresi).
              </div>
            </div>
          </div>
        )}

        {/* WATCHLIST */}
        {show("bandar screener") && (
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
