"""Stock routes: search, detail, K-line data."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import DailyKline, Stock
from app.models.user import User
from app.schemas.stock import KlineItem, KlineResponse, StockDetail, StockSearchResponse, StockSummary
from app.utils.security import get_current_user

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("", response_model=StockSearchResponse)
def search_stocks(
    q: str = Query("", description="Search query: code or name"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search stocks by code or name."""
    query = db.query(Stock).filter(Stock.is_active == 1)

    if q:
        query = query.filter(
            (Stock.code.like(f"%{q}%")) | (Stock.name.like(f"%{q}%"))
        )

    stocks = query.limit(limit).all()
    items = [
        StockSummary(code=s.code, name=s.name, exchange=s.exchange)
        for s in stocks
    ]
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
