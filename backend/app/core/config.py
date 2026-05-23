from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# 10 seed stocks used for quick validation (Tahap 0). yfinance uses ".JK".
SEED_TICKERS = [
    "BBCA", "BBRI", "BMRI", "BREN", "PANI",
    "CUAN", "AMMN", "MDKA", "SRTG", "TLKM",
]

# LQ45 — the 45 most liquid IDX names. Static snapshot (IDX rebalances ~biannually);
# treat as the working universe so breadth/dispersion are statistically meaningful.
LQ45_TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "ARTO", "BREN", "PANI", "CUAN", "AMMN",
    "MDKA", "SRTG", "TLKM", "ASII", "UNTR", "ADRO", "ADMR", "ANTM", "INCO", "PGAS",
    "PTBA", "ITMG", "MEDC", "AKRA", "ICBP", "INDF", "UNVR", "KLBF", "CPIN", "MYOR",
    "GGRM", "SMGR", "INTP", "CTRA", "PWON", "SMRA", "GOTO", "BUKA", "TOWR", "TBIG",
    "EXCL", "ISAT", "MAPI", "ACES", "AMRT",
]



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_ENV: str = "development"
    # Working universe: "lq45" (default) or "seed" (the 10 quick-test stocks).
    UNIVERSE: str = "lq45"
    # SBN 10Y yield (%) — no clean Yahoo feed, so set manually when it moves.
    SBN_10Y: float | None = None
    # Telegram alerts for high-conviction setups (optional).
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    # Portfolio risk defaults (IDR)
    ACCOUNT_SIZE_IDR: int = 500_000_000
    # IDX retail TIDAK bisa short. Long-only mode = skor negatif tidak menghasilkan
    # setup short, melainkan label AVOID/EXIT + waiting conditions untuk reversal.
    MARKET_MODE: str = "long_only"
    DATABASE_URL: str = "postgresql+psycopg://sahamflow:sahamflow@localhost:5432/sahamflow"
    REDIS_URL: str = "redis://localhost:6379/0"

    ANTHROPIC_API_KEY: str = ""
    # Default to a cost-effective Sonnet for narratives; override per-deployment.
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    ALLOWED_HOSTS: str = "*"
    TIMEZONE: str = "Asia/Jakarta"

    # Cost control: only generate AI narratives for the top-N composite scores.
    NARRATIVE_TOP_N: int = 50
    NARRATIVE_CACHE_TTL: int = 86400  # 1 day in seconds

    # === Smart filter / hedge fund discipline ===
    # Minimum R:R untuk lolos alert. < 1:2 = setup tidak layak risk.
    MIN_RR_RATIO: float = 2.0
    # Hari cooldown per ticker — hindari spam signal sama berturut-turut.
    COOLDOWN_DAYS: int = 3
    # Watchlist optional: comma-separated ticker (mis. "BBRI,ANTM,TLKM"). Kalau
    # diisi, hanya ticker di list yang akan kirim alert. Kosong = semua qualified.
    WATCHLIST_TICKERS: str = ""
    # Path ke file earnings calendar JSON. Format:
    # {"BBRI": {"earnings_date": "2026-05-28"}, ...}
    # Bot skip alert jika today dalam window ±EARNINGS_BLOCK_DAYS.
    EARNINGS_CALENDAR_PATH: str = ""
    EARNINGS_BLOCK_DAYS: int = 2

    @property
    def watchlist_set(self) -> set[str]:
        return {t.strip().upper() for t in self.WATCHLIST_TICKERS.split(",") if t.strip()}

    @property
    def allowed_origins(self) -> list[str]:
        if self.ALLOWED_HOSTS.strip() == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


    @property
    def universe(self) -> list[str]:
        return SEED_TICKERS if self.UNIVERSE == "seed" else LQ45_TICKERS


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
