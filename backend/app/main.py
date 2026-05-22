import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    backtest,
    brief,
    foreign_flow,
    regime,
    screener,
    sectors,
    stock,
    sync,
    trades,
)
from app.core.config import settings
from app.core.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Disable the scheduler in tests / one-off processes via env flag.
    if os.getenv("ENABLE_SCHEDULER", "1") == "1":
        start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Sahamflow API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
for module in (regime, screener, stock, foreign_flow, sectors, backtest, brief, trades, sync):
    app.include_router(module.router, prefix=API_PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.APP_ENV, "model": settings.CLAUDE_MODEL}
