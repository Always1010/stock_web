"""Watchlist schemas."""
from datetime import datetime

from pydantic import BaseModel


class WatchlistItemResponse(BaseModel):
    id: int
    code: str
    name: str
    exchange: str
    latest_close: float | None = None
    added_at: datetime

    model_config = {"from_attributes": True}


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItemResponse]
