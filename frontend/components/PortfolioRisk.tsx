"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { PortfolioRisk as PR } from "@/lib/types";

const fmtIDR = (n: number) => (n / 1e6).toFixed(1) + " jt";

export function PortfolioRiskPanel() {
  const [risk, setRisk] = useState<PR | null>(null);

  useEffect(() => {
    api.portfolioRisk().then((d) => d && setRisk(d));
  }, []);

  if (!risk) {
    return (
      <div className="pnl sec">
        <div className="pnl-h"><span className="pnl-t">Portfolio Risk Engine</span><span className="pnl-n">Loading...</span></div>
      </div>
    );
  }

  const heatPct = Math.min(100, (risk.portfolio_heat_pct / risk.heat_limit_pct) * 100);
  const overheat = risk.portfolio_heat_pct > risk.heat_limit_pct;
  const overcorr = risk.max_correlation != null && Math.abs(risk.max_correlation) > risk.correlation_limit;

  return (
    <div className="pnl sec">
      <div className="pnl-h">
        <span className="pnl-t">Portfolio Risk Engine</span>
        <span className="pnl-n">{risk.open_positions} posisi · gerbang trade</span>
        <div className="pnl-r"><span className="pdot" />LIVE</div>
      </div>
      <div className="rg">
        <div className="rgc">
          <div className="rg-l">Portfolio Heat</div>
          <div className={`rg-v mono ${overheat ? "dn" : ""}`}>{risk.portfolio_heat_pct}%</div>
          <div className="rg-bar"><div className={`rg-f ${overheat ? "w" : "s"}`} style={{ width: `${heatPct}%` }} /></div>
          <div className="rg-m">limit {risk.heat_limit_pct}% · {overheat ? "OVER — refuse new trades" : "aman"}</div>
        </div>
        <div className="rgc">
          <div className="rg-l">Open Risk</div>
          <div className="rg-v mono">{fmtIDR(risk.total_risk_idr)}</div>
          <div className="rg-m">total IDR di risiko</div>
        </div>
        <div className="rgc">
          <div className="rg-l">Max Correlation</div>
          <div className={`rg-v mono ${overcorr ? "dn" : ""}`}>{risk.max_correlation ?? "—"}</div>
          <div className="rg-m">{risk.max_correlation_pair ? risk.max_correlation_pair.join(" ↔ ") : "tidak cukup posisi"} · limit {risk.correlation_limit}</div>
        </div>
        <div className="rgc">
          <div className="rg-l">Account</div>
          <div className="rg-v mono">{fmtIDR(risk.account_size_idr)}</div>
          <div className="rg-m">untuk perhitungan heat</div>
        </div>
      </div>
      {Object.keys(risk.sector_concentration_pct).length > 0 && (
        <div className="pnl-b">
          <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
            KONSENTRASI SEKTOR · limit {risk.sector_limit_pct}%
          </div>
          {Object.entries(risk.sector_concentration_pct).map(([sec, pct]) => {
            const over = pct > risk.sector_limit_pct;
            return (
              <div className="szr" key={sec}>
                <span className="szl">{sec}</span>
                <span className={`szv mono ${over ? "dn" : ""}`}>{pct}%</span>
              </div>
            );
          })}
        </div>
      )}
      {risk.open_positions === 0 && (
        <div className="pnl-b" style={{ color: "var(--tx3)", fontSize: 11 }}>
          Belum ada posisi terbuka. Tambah trade via POST /api/v1/trades — heat & korelasi
          akan otomatis terhitung, dan engine akan menolak trade yang melampaui limit.
        </div>
      )}
    </div>
  );
}
