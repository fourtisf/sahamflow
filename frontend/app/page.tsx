"use client";

import { useEffect, useMemo, useState } from "react";
import { IhsgChart, EquityChart } from "@/components/Charts";
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

export default function Dashboard() {
  const [view, setView] = useState<View>("all");
  const [regime, setRegime] = useState<RegimeResponse | null>(null);
  const [rows, setRows] = useState<ScreenerRow[]>([]);
  const [live, setLive] = useState(false);
  const [indices, setIndices] = useState<Record<string, Quote> | null>(null);
  const [ihsg, setIhsg] = useState<{ closes: number[]; support: number | null; resistance: number | null; last: number | null } | null>(null);

  const [sel, setSel] = useState("BREN");
  const [modal, setModal] = useState("500.000.000");
  const [entry, setEntry] = useState("9.825");
  const [clock, setClock] = useState("");

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
    if (!STOCKS[sym]) return;
    setSel(sym);
    setEntry(fmtID(STOCKS[sym].price));
  }

  // Merge live screener rows over the prototype's stock ordering.
  const watch = useMemo(() => {
    const order = Object.keys(STOCKS);
    const byTicker = new Map(rows.map((r) => [r.ticker, r]));
    return order.map((t) => ({ ticker: t, live: byTicker.get(t) ?? null, meta: STOCKS[t] }));
  }, [rows]);

  const show = (grp: string) => view === "all" || grp.split(" ").includes(view);

  return (
    <>
      <nav className="nav">
        <div className="navin">
          <div className="brand">
            <div className="bmark">S</div>
            <div className="bname">Saham<span className="goldtext">flow</span></div>
          </div>
          <div className="ntabs">
            {TABS.map((t) => (
              <div key={t.v} className={`ntab${view === t.v ? " on" : ""}`} onClick={() => setView(t.v)}>
                {t.label}
              </div>
            ))}
          </div>
          <div className="nright">
            <div className="nstat">
              <span className="live" /><span className="hide">{live ? "DATA LIVE" : "IDX EOD"}</span><span>{clock}</span>
            </div>
            <div className="av">A</div>
          </div>
        </div>
      </nav>

      <div className="wrap">
        <div className="head">
          <div>
            <div className="htitle">Selamat datang, <span className="goldtext">ALFA</span></div>
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
            <div className="ix"><span className="ix-l">FOREIGN NET</span><span className="ix-v up mono">{regime?.foreign_flow_5d != null ? `${(regime.foreign_flow_5d / 1e9).toFixed(0)}B` : "n/a"}</span><span className="ix-c gd mono">5D</span></div>
          </div>
        </div>

        {/* REGIME */}
        <div className="pnl sec">
          <div className="pnl-h"><span className="pnl-t">Market Regime</span><span className="pnl-n">Multi-Factor Model</span><div className="pnl-r"><span className="pdot" />{live ? "LIVE" : "EOD"}</div></div>
          <div className="reg">
            <span className="reg-tag"><span className="d" /><span className="t">{(regime?.regime || "RISK-ON BULLISH").toUpperCase()}</span></span>
            <span className="reg-txt">
              Breadth <b>{regime?.breadth_ratio != null ? `${regime.breadth_ratio}×` : "—"}</b> ·{" "}
              Skor model <b>{regime?.raw_score ?? "—"}</b> · Multi-factor IHSG
            </span>
            <span className="reg-conf">CONFIDENCE <b>{regime?.confidence != null ? `${regime.confidence}%` : "—"}</b></span>
          </div>
          <div className="drv">
            <div className="dc"><div className="dc-l">A/D Ratio</div><div className="dc-v up mono">{regime?.breadth_ratio != null ? `${regime.breadth_ratio}×` : "—"}</div><div className="dc-m">Advance/decline</div></div>
            <div className="dc"><div className="dc-l">Foreign 5D</div><div className="dc-v up mono">{regime?.foreign_flow_5d != null ? `${(regime.foreign_flow_5d / 1e9).toFixed(0)}B` : "n/a"}</div><div className="dc-m">Butuh data IDX</div></div>
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

        {/* BANDAR + PREDICTOR */}
        {show("bandar screener") && (
          <div className="r2e sec">
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Bandar Detection</span><span className="pnl-n">Wyckoff · Estimasi</span><div className="pnl-r"><span className="pdot" />SCAN</div></div>
              <table className="dt">
                <thead><tr><th className="n">#</th><th>Sym</th><th className="r">Last</th><th>Phase</th><th className="r">Score</th></tr></thead>
                <tbody>
                  {watch.map((w, i) => (
                    <tr key={w.ticker} onClick={() => selectStock(w.ticker)}>
                      <td className="n">{i + 1}</td>
                      <td className="sym">{w.ticker}</td>
                      <td className="r mono">{fmtID(w.meta.price)}</td>
                      <td><span className={`ph ${phaseClass(w.live?.bandar_phase)}`}>{w.live?.bandar_phase || "Accum"}</span></td>
                      <td className={`scl ${scoreClass(w.live?.bandar_score)} mono`}>{w.live?.bandar_score ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Composite Signal</span><span className="pnl-n">Technical Score</span><div className="pnl-r"><span className="pdot" />{live ? "LIVE" : "EOD"}</div></div>
              <table className="dt">
                <thead><tr><th className="n">#</th><th>Sym</th><th className="r">Score</th><th>Signal</th></tr></thead>
                <tbody>
                  {watch.map((w, i) => (
                    <tr key={w.ticker} onClick={() => selectStock(w.ticker)}>
                      <td className="n">{i + 1}</td>
                      <td className="sym">{w.ticker}</td>
                      <td className={`r mono ${(w.live?.composite_score ?? 0) >= 0 ? "up" : "dn"}`}>{w.live?.composite_score ?? "—"}</td>
                      <td><span className={`sg ${(w.live?.composite_score ?? 0) >= 0.2 ? "sg-b" : (w.live?.composite_score ?? 0) <= -0.2 ? "sg-s" : "sg-h"}`}>{w.live?.signal || "—"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* RISK */}
        {show("risk") && (
          <>
            <div className="pnl sec">
              <div className="pnl-h"><span className="pnl-t">Risk Management</span><span className="pnl-n">Portfolio Heat</span><div className="pnl-r"><span className="pdot" />RT</div></div>
              <div className="rg">
                <div className="rgc"><div className="rg-l">Portfolio Heat</div><div className="rg-v mono">4.2%</div><div className="rg-bar"><div className="rg-f s" style={{ width: "42%" }} /></div><div className="rg-m">Total open risk · aman</div></div>
                <div className="rgc"><div className="rg-l">Max DD 30D</div><div className="rg-v dn mono">-3.8%</div><div className="rg-bar"><div className="rg-f s" style={{ width: "28%" }} /></div><div className="rg-m">Dalam batas 5%</div></div>
                <div className="rgc"><div className="rg-l">Konsentrasi Sektor</div><div className="rg-v mono">38%</div><div className="rg-bar"><div className="rg-f w" style={{ width: "76%" }} /></div><div className="rg-m">Energy berat · rebalance</div></div>
                <div className="rgc"><div className="rg-l">Sharpe 90D</div><div className="rg-v up mono">1.82</div><div className="rg-bar"><div className="rg-f s" style={{ width: "82%" }} /></div><div className="rg-m">Risk-adjusted kuat</div></div>
              </div>
            </div>
            <div className="rr sec">
              <div className="pnl">
                <div className="pnl-h"><span className="pnl-t">Position Sizer</span><span className="pnl-n">1% Risk · ATR×2 · 1:3</span></div>
                <div className="pnl-b">
                  <div className="szr"><span className="szl">Modal Tersedia</span><input className="szi" value={modal} onChange={(e) => setModal(e.target.value)} /></div>
                  <div className="szr"><span className="szl">Saham Target</span><input className="szi" value={sel} readOnly /></div>
                  <div className="szr"><span className="szl">Entry Price</span><input className="szi" value={entry} onChange={(e) => setEntry(e.target.value)} /></div>
                  <div className="szr"><span className="szl">Stop Loss (ATR×2)</span><span className="szv mono">{sizer?.sl ?? "—"}</span></div>
                  <div className="szr"><span className="szl">Take Profit (1:3)</span><span className="szv mono">{sizer?.tp ?? "—"}</span></div>
                  <div className="szr"><span className="szl">Risk/Trade (1%)</span><span className="szv mono">{sizer?.risk ?? "—"}</span></div>
                  <div className="szr"><span className="szl">Position Size</span><span className="szv up mono">{sizer?.pos ?? "—"}</span></div>
                </div>
              </div>
              <div className="pnl">
                <div className="pnl-h"><span className="pnl-t">Risk Alerts</span><span className="pnl-n">AI Engine</span></div>
                <div className="pnl-b">
                  <div className="alrt alrt-i"><b>► SIZING:</b> Risk 1%/trade + SL ATR-based → maks 5 posisi paralel tanpa lewati portfolio heat 6%.</div>
                  <div className="alrt alrt-w"><b>⚠ DATA:</b> Korelasi & heat real-time aktif penuh setelah journal terisi trade dan foreign flow tersedia.</div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* FUND + SENTIMENT */}
        {show("screener") && (
          <div className="r2e sec">
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Fundamental · <span>{sel}</span></span><span className="pnl-n">Quality {meta.qlty}</span></div>
              <div className="fg">
                <div className="fc"><span className="fc-n">PER</span><span className={`fc-v ${meta.perC} mono`}>{meta.per}</span></div>
                <div className="fc"><span className="fc-n">PBV</span><span className={`fc-v ${meta.pbvC} mono`}>{meta.pbv}</span></div>
                <div className="fc"><span className="fc-n">ROE</span><span className={`fc-v ${meta.roe.startsWith("-") ? "dn" : "up"} mono`}>{meta.roe}</span></div>
                <div className="fc"><span className="fc-n">DER</span><span className="fc-v up mono">{meta.der}</span></div>
                <div className="fc"><span className="fc-n">Rev YoY</span><span className={`fc-v ${meta.rev.startsWith("-") ? "dn" : "up"} mono`}>{meta.rev}</span></div>
                <div className="fc"><span className="fc-n">Net Margin</span><span className={`fc-v ${meta.nm.startsWith("-") ? "dn" : "up"} mono`}>{meta.nm}</span></div>
                <div className="fc"><span className="fc-n">Mkt Cap</span><span className="fc-v mono">{meta.mcap}</span></div>
                <div className="fc"><span className="fc-n">Earnings</span><span className="fc-v am mono">{meta.earn}</span></div>
              </div>
              <div className="pnl-b">
                {meta.flags.map((f, i) => (
                  <div className="flag" key={i}><span className={`fi fi-${f[0]}`}>{f[0] === "ok" ? "✓" : "!"}</span><div><b>{f[1]}</b> — {f[2]}</div></div>
                ))}
              </div>
            </div>
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Sentiment Engine</span><span className="pnl-n">Social + News 24H</span></div>
              <div className="pnl-b">
                <div className="sent">
                  <div className={`sent-v ${meta.sent >= 60 ? "up" : meta.sent <= 45 ? "dn" : "am"}`}>{meta.sent}</div>
                  <div className="sent-l">{meta.sentL}</div>
                  <div className="sent-bar"><div className="sent-mk" style={{ left: `${meta.sent}%` }} /></div>
                  <div className="sent-sc"><span>Fear</span><span>Netral</span><span>Greed</span></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* BACKTEST */}
        {show("backtest") && (
          <div className="pnl sec">
            <div className="pnl-h"><span className="pnl-t">Backtest Engine</span><span className="pnl-n">Composite · 2022-26</span></div>
            <div className="btg">
              <div className="btc"><div className="bt-l">Total Return</div><div className="bt-v up mono">+187.4%</div><div className="bt-m">IHSG +24.8%</div></div>
              <div className="btc"><div className="bt-l">Win Rate</div><div className="bt-v mono">64.2%</div><div className="bt-m">contoh</div></div>
              <div className="btc"><div className="bt-l">Sharpe</div><div className="bt-v up mono">1.92</div><div className="bt-m">Risk-adjusted</div></div>
              <div className="btc"><div className="bt-l">Max DD</div><div className="bt-v dn mono">-14.8%</div><div className="bt-m">Recover 38D</div></div>
              <div className="btc"><div className="bt-l">Avg Win</div><div className="bt-v up mono">+8.4%</div><div className="bt-m">Hold 5.2D</div></div>
              <div className="btc"><div className="bt-l">Avg Loss</div><div className="bt-v dn mono">-3.2%</div><div className="bt-m">SL active</div></div>
              <div className="btc"><div className="bt-l">Profit Factor</div><div className="bt-v up mono">2.64</div><div className="bt-m">2.64 : 1</div></div>
              <div className="btc"><div className="bt-l">Expectancy</div><div className="bt-v up mono">+3.28%</div><div className="bt-m">Per trade</div></div>
            </div>
            <div className="pnl-b"><div className="cw-sm"><EquityChart equity={EQUITY} benchmark={BENCHMARK} /></div></div>
            <div className="comp"><b>CATATAN:</b> Angka backtest di atas adalah contoh tampilan. Backtest live per saham tersedia via endpoint <b>/api/v1/backtest?ticker=BBCA</b> setelah data historis tersinkron.</div>
          </div>
        )}

        {/* JOURNAL */}
        {show("journal") && (
          <div className="rr sec">
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Trading Journal</span><span className="pnl-n">Auto-Tracked</span></div>
              <div className="pnl-b">
                <div className="alrt alrt-i"><b>► KOSONG:</b> Belum ada trade tercatat. Tambah lewat tombol "Trade Baru" atau endpoint <b>POST /api/v1/trades</b>. P&L akan otomatis terhitung & ter-atribusi.</div>
              </div>
            </div>
            <div className="pnl">
              <div className="pnl-h"><span className="pnl-t">Atribusi P&L</span><span className="pnl-n">30D</span></div>
              <div className="pnl-b">
                <div className="jst"><span className="jst-l">Sinyal Sahamflow</span><span className="jst-v mono">—</span></div>
                <div className="jst"><span className="jst-l">Intuisi/Diskresi</span><span className="jst-v mono">—</span></div>
                <div className="jst"><span className="jst-l">Net P&L Realized</span><span className="jst-v mono">—</span></div>
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
                <thead><tr><th className="n">#</th><th>Sym</th><th className="r">Last</th><th className="r">Score</th><th className="r">Bndr</th><th>Phase</th><th className="r">Frgn</th><th className="r">Qlty</th><th>Signal</th></tr></thead>
                <tbody>
                  {watch.map((w, i) => (
                    <tr key={w.ticker} onClick={() => selectStock(w.ticker)}>
                      <td className="n">{i + 1}</td>
                      <td className="sym">{w.ticker}</td>
                      <td className="r mono">{fmtID(w.meta.price)}</td>
                      <td className={`r mono ${(w.live?.composite_score ?? 0) >= 0 ? "up" : "dn"}`}>{w.live?.composite_score ?? "—"}</td>
                      <td className={`r ${scoreClass(w.live?.bandar_score)} mono`}>{w.live?.bandar_score ?? "—"}</td>
                      <td><span className={`ph ${phaseClass(w.live?.bandar_phase)}`}>{w.live?.bandar_phase || "—"}</span></td>
                      <td className="r mono fl">{w.live?.foreign_signal || "n/a"}</td>
                      <td className="r mono">{w.meta.qlty}</td>
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
