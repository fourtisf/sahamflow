"use client";

import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

type Candidate = {
  ticker: string;
  score: number;
  rsi: number;
  stoch_rsi: number;
  last_close: number;
  signatures: string[];
};

export function ReversalCandidates({ active }: { active: boolean }) {
  const [rows, setRows] = useState<Candidate[] | null>(null);

  useEffect(() => {
    fetch(`${BASE}/screener/reversals`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setRows(Array.isArray(d) ? d : []))
      .catch(() => setRows([]));
  }, []);

  return (
    <div className="pnl sec">
      <div className="pnl-h">
        <span className="pnl-t">Reversal Candidates</span>
        <span className="pnl-n">
          {active ? "regime mendukung — kandidat bottom-fishing" : "regime belum mendukung — daftar skor tinggi tetap ditampilkan"}
        </span>
        <div className="pnl-r"><span className="pdot" />LIVE</div>
      </div>
      {rows === null ? (
        <div className="pnl-b" style={{ color: "var(--tx3)" }}>Memindai universe…</div>
      ) : rows.length === 0 ? (
        <div className="pnl-b" style={{ color: "var(--tx3)", fontSize: 11 }}>
          Tidak ada saham dengan skor reversal ≥ 30 saat ini. Scanner menilai: RSI/StochRSI oversold,
          streak turun, reversal day, volume thrust di green close, bullish RSI divergence, gap closed.
        </div>
      ) : (
        <table className="dt">
          <thead>
            <tr>
              <th className="n">#</th>
              <th>Sym</th>
              <th className="r">Last</th>
              <th className="r">RSI</th>
              <th className="r">Score</th>
              <th>Signature</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c, i) => {
              const cls = c.score >= 70 ? "sc-h" : c.score >= 50 ? "sc-m" : "sc-l";
              return (
                <tr key={c.ticker}>
                  <td className="n">{i + 1}</td>
                  <td className="sym">{c.ticker}</td>
                  <td className="r mono">{c.last_close.toLocaleString("id-ID")}</td>
                  <td className="r mono" style={{ color: c.rsi < 30 ? "var(--grn)" : "var(--tx2)" }}>{c.rsi}</td>
                  <td className={`r scl ${cls} mono`}>{c.score}</td>
                  <td style={{ fontSize: 10.5, color: "var(--tx2)" }}>{c.signatures.join(" · ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
