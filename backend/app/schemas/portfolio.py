"""Portfolio schemas."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class PortfolioUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class PortfolioSummary(BaseModel):
    code: str
    name: str
    created_at: datetime
    return_start_date: date | None = None
    latest_nav: float | None = None
    latest_cumulative_return: float | None = None
    latest_return_rate: float | None = None

    model_config = {"from_attributes": True}


class HoldingResponse(BaseModel):
    id: int
    stock_code: str
    stock_name: str
    shares: float
    cost_price: float | None = None
    cost_price_set_at: datetime | None = None
    is_cost_locked: bool
    current_price: float | None = None
    return_amount: float | None = None
    return_rate: float | None = None

    model_config = {"from_attributes": True}


class PortfolioDetail(BaseModel):
    code: str
    name: str
    created_at: datetime
    updated_at: datetime
    return_start_date: date | None = None
    holdings: list[HoldingResponse]
    latest_nav: float | None = None
    latest_cumulative_return: float | None = None
    latest_return_rate: float | None = None

    model_config = {"from_attributes": True}


class AddHoldingRequest(BaseModel):
    stock_code: str = Field(..., min_length=6, max_length=6)
    shares: float = Field(..., gt=0)
    cost_price: float | None = Field(None, gt=0)


class UpdateHoldingRequest(BaseModel):
    shares: float = Field(..., gt=0)


class SetCostPriceRequest(BaseModel):
    cost_price: float = Field(..., gt=0)


class NavHistoryItem(BaseModel):
    date: str
    nav: float
    daily_return: float | None = None
    daily_return_rate: float | None = None
    cum_return_rate: float | None = None
    total_cost: float
    total_market_value: float


class NavHistoryResponse(BaseModel):
    portfolio_code: str
    portfolio_name: str
    data: list[NavHistoryItem]


class DailyReturnItem(BaseModel):
    date: str
    return_amount: float | None = None
    return_rate: float | None = None


class DailyReturnsResponse(BaseModel):
    portfolio_code: str
    year: int
    month: int | None = None
    data: list[DailyReturnItem]


class MonthlyReturnItem(BaseModel):
    month: int
    return_amount: float | None = None
    return_rate: float | None = None


class MonthlyReturnsResponse(BaseModel):
    portfolio_code: str
    year: int
    data: list[MonthlyReturnItem]


class ContributionItem(BaseModel):
    stock_code: str
    stock_name: str
    shares: float
    cost_price: float | None = None
    start_price: float | None = None
    end_price: float | None = None
    market_value: float
    return_amount: float | None = None
    return_rate: float | None = None
    contribution_pct: float | None = None


class ContributionResponse(BaseModel):
    portfolio_code: str
    start_date: str
    end_date: str
    data: list[ContributionItem]


# ── Return Start Date ───────────────────────────────────────────

class SetReturnStartDateRequest(BaseModel):
    return_start_date: date | None = None


# ── Portfolio Refresh ───────────────────────────────────────────

class PortfolioRefreshResponse(BaseModel):
    portfolio_code: str
    total_stocks: int
    processed: int
    total_affected: int
    errors: int
    message: str = ""


class PortfolioNavRecalcResponse(BaseModel):
    portfolio_code: str
    start_date: str | None = None
    end_date: str
    records_created: int
    message: str = ""
