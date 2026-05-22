# Sahamflow — Data Sources (Tahap 0)

Data quality is the foundation: wrong data → wrong signals. This document records
the options evaluated for IDX (Bursa Efek Indonesia) market data, a live test of
the MVP source, and the recommendation.

## Options evaluated

| Source | Coverage | Cost | Latency | Legality | MVP fit |
|---|---|---|---|---|---|
| **yfinance (Yahoo)** | OHLCV per ticker (`BBCA.JK`) | Free | EOD, ~15 min delayed | OK for personal use | **Primary** |
| IDX official scrape (`idx.co.id/market-data`) | Foreign flow, EOD | Free | EOD | Legal, needs automation | Tahap 3 |
| RTI / Stockbit scrape | Broker summary | Free | Intraday | **Legal gray area — warn owner** | Avoid for MVP |
| Stockbit Data / RTI Business (paid) | Broker summary, real-time | Paid | Real-time | Licensed | Fase 2 |

## What yfinance gives us — and what it does NOT

- **Gives:** open/high/low/close/volume per IDX ticker via the `.JK` suffix.
- **Does NOT give:** foreign buy/sell flow, broker summary. These power the
  Foreign Flow panel and precise Bandar detection.

Consequence baked into the code:
- `foreign_net` columns stay `NULL` until the IDX scraper (Tahap 3) feeds them.
- `/foreign-flow/today` returns `has_data: false` per ticker rather than guessing.
- Bandar detection runs as a **proxy** (price + volume + foreign-when-available)
  and every result is flagged `estimated: true`, surfaced honestly in the UI.

## Live validation

yfinance ticker formats and IDX availability change occasionally. Validate before
relying on it:

```bash
cd backend
python -m scripts.fetch_seed --check
```

This checks all 10 seed tickers (BBCA, BBRI, BMRI, BREN, PANI, CUAN, AMMN, MDKA,
SRTG, TLKM) and prints row counts + last close. Record the result here when run on
the deployment host:

```
# (paste latest `--check` output here on first deploy)
```

> Note: this validation requires outbound network access to Yahoo Finance. In the
> sandboxed CI/build environment that may be blocked; run it on the VPS.

## Recommendation

1. **MVP:** yfinance for OHLCV across the 10 seed stocks, EOD sync at 17:30 WIB.
2. **Tahap 3:** add the IDX official scraper for foreign flow (legal, EOD).
3. **Fase 2:** move to a paid broker-summary feed for precise bandar detection.
4. Never scrape RTI/Stockbit for production without confirming licensing with the
   owner — flagged as legal gray area.
