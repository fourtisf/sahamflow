"use client";

import { useEffect, useRef, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

type Hit = { ticker: string; name: string; sector: string };

export function StockSearch({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) {
      setHits([]);
      return;
    }
    let alive = true;
    const id = setTimeout(() => {
      fetch(`${BASE}/search?q=${encodeURIComponent(q)}&limit=15`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : []))
        .then((d) => alive && setHits(Array.isArray(d) ? d : []))
        .catch(() => alive && setHits([]));
    }, 120);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [q]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pick(h: Hit) {
    setQ("");
    setHits([]);
    setOpen(false);
    onSelect(h.ticker);
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || !hits.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(hits[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={wrapRef} style={{ position: "relative", flex: "1 1 auto", maxWidth: 360, marginRight: 12 }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKey}
        placeholder="🔍 Cari saham (BBCA, GOTO, AMMN, ...)"
        style={{
          width: "100%",
          background: "var(--panel)",
          border: "1px solid var(--line2)",
          color: "var(--tx)",
          padding: "7px 12px",
          borderRadius: 8,
          fontFamily: "inherit",
          fontSize: 12,
        }}
      />
      {open && hits.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            marginTop: 4,
            background: "var(--panel)",
            border: "1px solid var(--line2)",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
            maxHeight: 360,
            overflowY: "auto",
            zIndex: 200,
          }}
        >
          {hits.map((h, i) => (
            <div
              key={h.ticker}
              onMouseDown={() => pick(h)}
              onMouseEnter={() => setActive(i)}
              style={{
                padding: "8px 12px",
                cursor: "pointer",
                background: i === active ? "var(--panel2)" : "transparent",
                borderBottom: "1px solid var(--line)",
                display: "flex",
                gap: 10,
                alignItems: "center",
              }}
            >
              <span className="sym mono" style={{ minWidth: 56 }}>{h.ticker}</span>
              <span style={{ flex: 1, fontSize: 11, color: "var(--tx2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {h.name}
              </span>
              <span style={{ fontSize: 9.5, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h.sector}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
