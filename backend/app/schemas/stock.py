"""Stock schemas."""
from datetime import date

from pydantic import BaseModel


class StockSummary(BaseModel):
    code: str
    name: str
    exchange: str
    latest_close: float | None = None
    change_pct: float | None = None

    model_config = {"from_attributes": True}


class StockDetail(BaseModel):
    code: str
    name: str
    exchange: str
    is_active: int

    model_config = {"from_attributes": True}


class KlineItem(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class KlineResponse(BaseModel):
    code: str
    name: str
    data: list[KlineItem]


class StockSearchResponse(BaseModel):
    items: list[StockSummary]
