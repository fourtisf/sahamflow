"""Sync pipeline: pull OHLCV, compute regime, generate signals (Tahap 0/1/2/3).

These functions are called both by the cron scheduler and the admin sync
endpoints. Everything is upsert-based so re-running a day is idempotent.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.data_sources import yahoo_finance as yf
from app.models import OHLCVDaily, RegimeHistory, SignalCache, Stock
from app.services import (
    bandar_detector,
    foreign_flow_analyzer,
    market_signals,
    regime_classifier,
    technical_analysis,
)


log = logging.getLogger("sahamflow.data_sync")


def seed_stocks(tickers: list[str] | None = None) -> int:
    tickers = tickers or settings.universe
    count = 0
    with SessionLocal() as db:
        for t in tickers:
            info = yf.fetch_info(t)
            stmt = insert(Stock).values(
                ticker=info["ticker"],
                name=info.get("name"),
                sector=info.get("sector"),
                market_cap=info.get("market_cap"),
                is_active=True,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "name": stmt.excluded.name,
                    "sector": stmt.excluded.sector,
                    "market_cap": stmt.excluded.market_cap,
                },
            )
            db.execute(stmt)
            count += 1
        db.commit()
    return count


def sync_ohlcv(tickers: list[str] | None = None, period: str = "1mo") -> dict:
    tickers = tickers or settings.universe
    summary: dict[str, int] = {}
    with SessionLocal() as db:
        for t in tickers:
            records = yf.fetch_ohlcv_records(t, period=period)
            for rec in records:
                stmt = insert(OHLCVDaily).values(**rec)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ticker", "date"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                        "value": stmt.excluded.value,
                    },
                )
                db.execute(stmt)
            summary[t] = len(records)
        db.commit()

    # QA gate: do not let a silent empty/stale sync pass unnoticed.
    empties = [t for t, n in summary.items() if n == 0]
    if empties:
        log.warning(
            "OHLCV sync: %d/%d tickers returned 0 rows: %s",
            len(empties), len(summary), ", ".join(empties),
        )
    if summary and len(empties) == len(summary):
        log.error("OHLCV sync: ALL tickers empty — data source likely down.")
    return {"rows": summary, "empty": empties, "ok": bool(summary) and len(empties) < len(summary)}


def load_ohlcv_df(db: Session, ticker: str, days: int = 250) -> pd.DataFrame:
    rows = db.execute(
        select(OHLCVDaily)
        .where(OHLCVDaily.ticker == ticker)
        .order_by(OHLCVDaily.date)
    ).scalars().all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        [
            {
                "date": r.date,
                "open": float(r.open) if r.open is not None else None,
                "high": float(r.high) if r.high is not None else None,
                "low": float(r.low) if r.low is not None else None,
                "close": float(r.close) if r.close is not None else None,
                "volume": int(r.volume) if r.volume is not None else 0,
                "foreign_net": r.foreign_net,
            }
            for r in rows
        ]
    ).set_index("date")
    return df.tail(days)


def sync_foreign_flow(target_date: date | None = None) -> dict:
    """Best-effort pull of foreign buy/sell from idx.co.id daily summary.

    Updates the existing OHLCV rows in-place. Silently returns {scraped: 0}
    if IDX endpoint is down — no fabricated data.
    """
    from app.data_sources import idx_scraper

    target = target_date or date.today()
    rows = idx_scraper.fetch_foreign_flow(target)
    updated = 0
    with SessionLocal() as db:
        for rec in rows:
            res = db.execute(
                OHLCVDaily.__table__.update()
                .where(
                    (OHLCVDaily.ticker == rec["ticker"])
                    & (OHLCVDaily.date == rec["date"])
                )
                .values(
                    foreign_buy=rec["foreign_buy"],
                    foreign_sell=rec["foreign_sell"],
                    foreign_net=rec["foreign_net"],
                )
            )
            updated += res.rowcount or 0
        db.commit()
    log.info("Foreign flow sync %s: scraped=%d updated=%d", target, len(rows), updated)
    return {"scraped": len(rows), "updated": updated, "date": str(target)}


def generate_signals(tickers: list[str] | None = None, on: date | None = None) -> dict:
    tickers = tickers or settings.universe
    on = on or date.today()
    summary: dict[str, float] = {}
    with SessionLocal() as db:
        for t in tickers:
            df = load_ohlcv_df(db, t)
            if df.empty or len(df) < 20:
                continue
            score, indicators = technical_analysis.composite_score(df)
            foreign_5d = (
                int(df["foreign_net"].dropna().tail(5).sum())
                if df["foreign_net"].notna().any()
                else None
            )
            bandar = bandar_detector.detect(df, foreign_5d)
            ff = foreign_flow_analyzer.analyze(list(df["foreign_net"]))

            stmt = insert(SignalCache).values(
                ticker=t,
                date=on,
                composite_score=round(score, 3),
                indicators={**indicators, "signal_label": technical_analysis.signal_label(score)},
                foreign_signal=ff.get("signal") if ff.get("has_data") else None,
                bandar_phase=bandar["phase"],
                bandar_score=bandar["score"],
                ai_predict=None,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "date"],
                set_={
                    "composite_score": stmt.excluded.composite_score,
                    "indicators": stmt.excluded.indicators,
                    "foreign_signal": stmt.excluded.foreign_signal,
                    "bandar_phase": stmt.excluded.bandar_phase,
                    "bandar_score": stmt.excluded.bandar_score,
                },
            )
            db.execute(stmt)
            summary[t] = round(score, 3)
        db.commit()
    return summary


def compute_regime(on: date | None = None) -> dict:
    """Compute the regime from universe breadth + (when available) foreign flow.

    With the Yahoo-only MVP, foreign/fx/yield/dispersion inputs are sparse, so the
    regime leans on breadth and MA200 position. Sparse factors stay 0 (neutral)
    rather than being fabricated.
    """
    on = on or date.today()
    with SessionLocal() as db:
        advances = declines = 0
        ma200_signals: list[float] = []
        ret_5d: list[float] = []
        foreign_5d_total = 0
        has_foreign = False

        for t in settings.universe:
            df = load_ohlcv_df(db, t)
            if df.empty or len(df) < 2:
                continue
            if df["close"].iloc[-1] >= df["close"].iloc[-2]:
                advances += 1
            else:
                declines += 1
            ma200 = df["close"].rolling(min(200, len(df))).mean().iloc[-1]
            ma200_signals.append(
                regime_classifier.norm_ma200(df["close"].iloc[-1], ma200)
            )
            if len(df) >= 6 and df["close"].iloc[-6]:
                ret_5d.append((df["close"].iloc[-1] / df["close"].iloc[-6] - 1) * 100)
            if df["foreign_net"].notna().any():
                has_foreign = True
                foreign_5d_total += int(df["foreign_net"].dropna().tail(5).sum())

        # Real macro: USD/IDR 30d trend; sector/stock dispersion of 5d returns.
        try:
            fx_chg = yf.usdidr_change_pct_30d()
        except Exception:
            fx_chg = None
        dispersion_5d = (
            float(pd.Series(ret_5d).std()) if len(ret_5d) >= 5 else None
        )

        factors = {
            "breadth": regime_classifier.norm_breadth(advances, declines),
            "foreign": regime_classifier.norm_foreign(foreign_5d_total) if has_foreign else 0.0,
            "ma200": sum(ma200_signals) / len(ma200_signals) if ma200_signals else 0.0,
            "fx": regime_classifier.norm_fx(fx_chg) if fx_chg is not None else 0.0,
            "yield": regime_classifier.norm_yield(settings.SBN_10Y) if settings.SBN_10Y else 0.0,
            "dispersion": regime_classifier.norm_dispersion(dispersion_5d) if dispersion_5d is not None else 0.0,
        }
        result = regime_classifier.classify_regime(factors)

        # Path-aware modifier from IHSG OHLC (8-day streaks, reversal, gap-fill,
        # 30/90d returns). Distinguishes "Distribution from top" vs
        # "Markdown capitulation" vs "Potential Accumulation".
        try:
            ihsg_bars = yf.fetch_ohlc_history("^JKSE", period="3mo")
            path = market_signals.regime_path_modifier(ihsg_bars) if ihsg_bars else {"modifier": None, "signals": {}}
        except Exception:
            path = {"modifier": None, "signals": {}}
        result["modifier"] = path["modifier"]
        result["path_signals"] = path["signals"]

        stmt = insert(RegimeHistory).values(
            date=on,
            regime=result["regime"],
            confidence=result["confidence"],
            breadth_ratio=round(advances / declines, 2) if declines else None,
            foreign_flow_5d=foreign_5d_total if has_foreign else None,
            raw_score=result["raw_score"],
            extra={
                "factors": result["factors"],
                "advances": advances,
                "declines": declines,
                "modifier": result.get("modifier"),
                "path_signals": result.get("path_signals", {}),
            },
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={
                "regime": stmt.excluded.regime,
                "confidence": stmt.excluded.confidence,
                "breadth_ratio": stmt.excluded.breadth_ratio,
                "foreign_flow_5d": stmt.excluded.foreign_flow_5d,
                "raw_score": stmt.excluded.raw_score,
                "metadata": stmt.excluded.metadata,
            },
        )
        db.execute(stmt)
        db.commit()
        return {**result, "advances": advances, "declines": declines}
