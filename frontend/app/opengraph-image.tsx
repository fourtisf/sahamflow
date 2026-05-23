import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Sahamflow — Analitik Saham IHSG untuk Trader Retail";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(255,210,74,0.18), transparent 60%), #000",
          display: "flex",
          flexDirection: "column",
          padding: "80px",
          fontFamily: "system-ui, sans-serif",
          color: "#f5f5f3",
        }}
      >
        {/* Top: logo mark + brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div
            style={{
              width: 96,
              height: 96,
              borderRadius: 22,
              background: "linear-gradient(135deg, #ffe699, #ffd24a 45%, #c79a2e)",
              boxShadow: "0 0 60px rgba(255,210,74,0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 64,
              fontWeight: 800,
              color: "#1a1200",
            }}
          >
            S
          </div>
          <div style={{ fontSize: 64, fontWeight: 800, letterSpacing: "-3px", display: "flex" }}>
            <span>Saham</span>
            <span
              style={{
                background: "linear-gradient(135deg, #ffe699, #ffd24a 45%, #c79a2e)",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              flow
            </span>
          </div>
        </div>

        {/* Middle: tagline */}
        <div
          style={{
            marginTop: 80,
            fontSize: 56,
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-2px",
            maxWidth: 1000,
          }}
        >
          Analitik Saham IHSG buy-side untuk
          <span style={{ color: "#ffd24a" }}> trader retail</span>
        </div>

        {/* Bottom: features pills */}
        <div style={{ marginTop: "auto", display: "flex", gap: 16, flexWrap: "wrap" }}>
          {[
            "Market Regime",
            "Smart Money Proxy",
            "Reversal Scanner",
            "Walk-Forward Backtest",
            "ATR Levels",
          ].map((p) => (
            <div
              key={p}
              style={{
                padding: "14px 26px",
                borderRadius: 12,
                background: "#0a0a0b",
                border: "1px solid #242428",
                fontSize: 24,
                color: "#a8a8a2",
              }}
            >
              {p}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ marginTop: 40, fontSize: 22, color: "#6e6e68", display: "flex", justifyContent: "space-between" }}>
          <span>sahamflow.com</span>
          <span>Long-only IDX · Data, bukan rekomendasi</span>
        </div>
      </div>
    ),
    size,
  );
}
