"""Market overview schemas."""
from pydantic import BaseModel


class IndexItem(BaseModel):
    code: str
    name: str
    close: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    trade_date: str

    model_config = {"from_attributes": True}


class IndicesResponse(BaseModel):
    data: list[IndexItem]
    trade_date: str


class BreadthItem(BaseModel):
    board: str
    board_label: str
    total: int
    up_count: int
    down_count: int
    flat_count: int
    trade_date: str

    model_config = {"from_attributes": True}


class BreadthResponse(BaseModel):
    data: list[BreadthItem]
    trade_date: str


class SectorItem(BaseModel):
    code: str
    name: str
    change_pct: float
    leading_stock: str | None = None
    leading_stock_change: float | None = None
    rank: int

    model_config = {"from_attributes": True}


class SectorResponse(BaseModel):
    data: list[SectorItem]
    trade_date: str
