"""Hardcoded sector mapping untuk LQ45 — fallback ketika Stock.sector NULL.

yfinance untuk IDX sering return sector kosong. Mapping ini di-curate manual
berdasar klasifikasi IDX (IDX-IC). Update bila ada rotation/listing baru.
"""

from __future__ import annotations

LQ45_SECTORS: dict[str, str] = {
    # Financials
    "BBCA": "Financials", "BBRI": "Financials", "BMRI": "Financials",
    "BBNI": "Financials", "BRIS": "Financials", "ARTO": "Financials",

    # Energy (coal, oil & gas)
    "ADRO": "Energy", "ADMR": "Energy", "ITMG": "Energy", "PTBA": "Energy",
    "MEDC": "Energy", "AKRA": "Energy", "PGAS": "Energy",

    # Basic Materials (mining, chemicals)
    "ANTM": "Materials", "INCO": "Materials", "MDKA": "Materials",
    "AMMN": "Materials", "BREN": "Materials",

    # Industrials
    "ASII": "Industrials", "UNTR": "Industrials", "SMGR": "Industrials",
    "INTP": "Industrials",

    # Consumer Non-Cyclicals (food, tobacco, household)
    "ICBP": "Consumer-NC", "INDF": "Consumer-NC", "UNVR": "Consumer-NC",
    "CPIN": "Consumer-NC", "MYOR": "Consumer-NC", "GGRM": "Consumer-NC",
    "AMRT": "Consumer-NC",

    # Consumer Cyclicals (retail, auto)
    "MAPI": "Consumer-Cyc", "ACES": "Consumer-Cyc",

    # Healthcare
    "KLBF": "Healthcare",

    # Property & Real Estate
    "CTRA": "Property", "PWON": "Property", "SMRA": "Property",

    # Technology
    "GOTO": "Technology", "BUKA": "Technology",

    # Communication Services
    "TLKM": "Telecom", "ISAT": "Telecom", "EXCL": "Telecom",
    "TOWR": "Telecom", "TBIG": "Telecom",

    # Infrastructure / Investment / Holding
    "SRTG": "Investment", "PANI": "Investment", "CUAN": "Investment",
}


def get_sector(ticker: str) -> str:
    """Return sector for ticker, fallback 'Unknown'."""
    return LQ45_SECTORS.get(ticker.upper(), "Unknown")
