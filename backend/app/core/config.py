from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


# 10 seed stocks for the MVP universe (Tahap 0). yfinance uses the ".JK" suffix.
SEED_TICKERS = [
    "BBCA",
    "BBRI",
    "BMRI",
    "BREN",
    "PANI",
    "CUAN",
    "AMMN",
    "MDKA",
    "SRTG",
    "TLKM",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_ENV: str = "development"
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

    @property
    def allowed_origins(self) -> list[str]:
        if self.ALLOWED_HOSTS.strip() == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
