"""Stock routes: search, detail, K-line data."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sqla_func

from app.database import get_db
from app.models.stock import DailyKline, Stock
from app.models.user import User
from app.schemas.stock import KlineItem, KlineResponse, StockDetail, StockSearchResponse, StockSummary
from app.utils.security import get_current_user

router = APIRouter(prefix="/stocks", tags=["Stocks"])


def _get_price_info(stock_id: int, db: Session) -> tuple[float | None, float | None]:
    """Get latest close and change% for a stock. Returns (close, change_pct)."""
    latest = (
        db.query(DailyKline)
        .filter(DailyKline.stock_id == stock_id)
        .order_by(DailyKline.trade_date.desc())
        .first()
    )
    if not latest:
        return None, None

    prev = (
        db.query(DailyKline)
        .filter(DailyKline.stock_id == stock_id, DailyKline.trade_date < latest.trade_date)
        .order_by(DailyKline.trade_date.desc())
        .first()
    )
    if not prev or prev.close == 0:
        return latest.close, None

    change_pct = round((latest.close - prev.close) / prev.close * 100, 2)
    return latest.close, change_pct


@router.get("", response_model=StockSearchResponse)
def search_stocks(
    q: str = Query("", description="Search query: code or name"),
    limit: int | None = Query(None, ge=1, le=500, description="Max results, omit for all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search stocks by code or name. Returns all matches unless limit is set."""
    query = db.query(Stock).filter(Stock.is_active == 1)

    if q:
        query = query.filter(
            (Stock.code.like(f"%{q}%")) | (Stock.name.like(f"%{q}%"))
        )

    stocks = query.limit(limit).all() if limit else query.all()
    items = []
    for s in stocks:
        close, change_pct = _get_price_info(s.id, db)
        items.append(StockSummary(
            code=s.code, name=s.name, exchange=s.exchange,
            latest_close=close, change_pct=change_pct,
        ))
    return StockSearchResponse(items=items)


@router.get("/count")
def count_stocks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total count of active stocks."""
    count = db.query(Stock).filter(Stock.is_active == 1).count()
    return {"count": count}


@router.get("/{code}", response_model=StockDetail)
def get_stock(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stock detail by code."""
    stock = db.query(Stock).filter(Stock.code == code, Stock.is_active == 1).first()
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    return stock


@router.get("/{code}/kline", response_model=KlineResponse)
def get_kline(
    code: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily K-line data for a stock."""
    stock = db.query(Stock).filter(Stock.code == code, Stock.is_active == 1).first()
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    query = db.query(DailyKline).filter(DailyKline.stock_id == stock.id)

    if start:
        query = query.filter(DailyKline.trade_date >= date.fromisoformat(start))
    if end:
        query = query.filter(DailyKline.trade_date <= date.fromisoformat(end))

    klines = query.order_by(DailyKline.trade_date.asc()).all()

    # If no data in DB, try to crawl on demand
    if not klines:
        from app.services.crawler import crawl_kline_on_demand
        klines = crawl_kline_on_demand(stock, db, start, end)
        if not klines:
            klines = []
            # Still try to query again after crawl
            query2 = db.query(DailyKline).filter(DailyKline.stock_id == stock.id)
            if start:
                query2 = query2.filter(DailyKline.trade_date >= date.fromisoformat(start))
            if end:
                query2 = query2.filter(DailyKline.trade_date <= date.fromisoformat(end))
            klines = query2.order_by(DailyKline.trade_date.asc()).all()

    data = [
        KlineItem(
            date=k.trade_date.isoformat(),
            open=k.open,
            high=k.high,
            low=k.low,
            close=k.close,
            volume=k.volume,
            amount=k.amount,
        )
        for k in klines
    ]

    return KlineResponse(code=stock.code, name=stock.name, data=data)
