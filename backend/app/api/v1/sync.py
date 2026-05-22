from fastapi import APIRouter

from app.services import data_sync

router = APIRouter(tags=["admin-sync"])


@router.post("/sync/seed")
def sync_seed():
    """Seed the stocks table with metadata for the universe."""
    return {"seeded": data_sync.seed_stocks()}


@router.post("/sync/ohlcv")
def sync_ohlcv(period: str = "1mo"):
    return {"synced": data_sync.sync_ohlcv(period=period)}


@router.post("/sync/regime")
def sync_regime():
    return data_sync.compute_regime()


@router.post("/generate/signals")
def generate_signals():
    return {"signals": data_sync.generate_signals()}
