from fastapi import APIRouter, Query

from app.data import idx_tickers

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str = Query("", min_length=0), limit: int = 20):
    """Autocomplete search saham IDX. Match prefix > substring di ticker > nama."""
    return idx_tickers.search(q, limit=limit)
