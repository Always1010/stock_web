"""Market overview routes: indices, breadth, sectors."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market import IndexKline, MarketBreadth, MarketIndex, MarketTurnover, SectorData
from app.models.user import User
from app.schemas.market import (
    BreadthItem,
    BreadthResponse,
    IndexItem,
    IndicesResponse,
    SectorItem,
    SectorResponse,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/market", tags=["Market"])

BOARD_LABELS = {"SH": "沪市主板", "SZ": "深市主板", "BJ": "北交所"}


@router.post("/refresh")
def refresh_market(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-crawl market indices, breadth, sectors, and turnover data."""
    from app.services.crawler import (
        crawl_market_breadth,
        crawl_market_indices,
        crawl_sectors,
        crawl_market_turnover,
    )

    results = {}
    try:
        results["indices"] = crawl_market_indices(db)
    except Exception as e:
        results["indices"] = {"error": str(e)}
    try:
        results["breadth"] = crawl_market_breadth(db)
    except Exception as e:
        results["breadth"] = {"error": str(e)}
    try:
        results["sectors"] = crawl_sectors(db)
    except Exception as e:
        results["sectors"] = {"error": str(e)}
    try:
        results["turnover"] = crawl_market_turnover(db)
    except Exception as e:
        results["turnover"] = {"error": str(e)}

    return {"message": "Market data refreshed", "results": results}


@router.get("/indices", response_model=IndicesResponse)
def get_indices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest major A-share index quotes."""
    # Get the most recent trade date
    latest = (
        db.query(MarketIndex)
        .order_by(MarketIndex.trade_date.desc())
        .first()
    )
    if not latest:
        return IndicesResponse(data=[], trade_date="")

    trade_date = latest.trade_date
    indices = (
        db.query(MarketIndex)
        .filter(MarketIndex.trade_date == trade_date)
        .order_by(MarketIndex.code)
        .all()
    )

    data = [
        IndexItem(
            code=m.code,
            name=m.name,
            close=m.close,
            change=m.change,
            change_pct=m.change_pct,
            open=m.open,
            high=m.high,
            low=m.low,
            trade_date=m.trade_date.isoformat(),
        )
        for m in indices
    ]
    return IndicesResponse(data=data, trade_date=trade_date.isoformat())


@router.get("/breadth", response_model=BreadthResponse)
def get_breadth(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get market breadth (up/down/flat counts) for the latest trading day."""
    latest = (
        db.query(MarketBreadth)
        .order_by(MarketBreadth.trade_date.desc())
        .first()
    )
    if not latest:
        return BreadthResponse(data=[], trade_date="")

    trade_date = latest.trade_date
    records = (
        db.query(MarketBreadth)
        .filter(MarketBreadth.trade_date == trade_date)
        .order_by(MarketBreadth.board)
        .all()
    )

    data = [
        BreadthItem(
            board=r.board,
            board_label=BOARD_LABELS.get(r.board, r.board),
            total=r.total,
            up_count=r.up_count,
            down_count=r.down_count,
            flat_count=r.flat_count,
            trade_date=r.trade_date.isoformat(),
        )
        for r in records
    ]

    # Add ALL aggregate
    if data:
        all_total = sum(d.total for d in data)
        all_up = sum(d.up_count for d in data)
        all_down = sum(d.down_count for d in data)
        all_flat = sum(d.flat_count for d in data)
        data.insert(0, BreadthItem(
            board="ALL", board_label="全市场",
            total=all_total, up_count=all_up,
            down_count=all_down, flat_count=all_flat,
            trade_date=trade_date.isoformat(),
        ))

    return BreadthResponse(data=data, trade_date=trade_date.isoformat())


@router.get("/sectors", response_model=SectorResponse)
def get_sectors(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get sector rankings for the latest trading day."""
    latest = (
        db.query(SectorData)
        .order_by(SectorData.trade_date.desc())
        .first()
    )
    if not latest:
        return SectorResponse(data=[], trade_date="")

    trade_date = latest.trade_date
    sectors = (
        db.query(SectorData)
        .filter(SectorData.trade_date == trade_date)
        .order_by(SectorData.rank.asc())
        .limit(limit)
        .all()
    )

    data = [
        SectorItem(
            code=s.code,
            name=s.name,
            change_pct=s.change_pct,
            leading_stock=s.leading_stock,
            leading_stock_change=s.leading_stock_change,
            rank=s.rank,
        )
        for s in sectors
    ]
    return SectorResponse(data=data, trade_date=trade_date.isoformat())


@router.post("/indices/{code}/refresh")
def refresh_index_kline(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-crawl K-line data for a market index, overwriting existing records."""
    from app.services.crawler import crawl_index_kline

    cfg = {c["code"]: c for c in [
        {"code": "sh000001", "name": "上证指数"},
        {"code": "sz399001", "name": "深证成指"},
        {"code": "sz399006", "name": "创业板指"},
        {"code": "sh000688", "name": "科创50"},
        {"code": "sh000300", "name": "沪深300"},
    ]}
    info = cfg.get(code)
    if not info:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown index: {code}")

    affected = crawl_index_kline(code, info["name"], db, overwrite=True)
    return {"code": code, "affected": affected, "message": f"Refreshed {affected} records for {code}"}


@router.get("/indices/{code}/kline", response_model=None)
def get_index_kline(
    code: str,
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get K-line data for a market index."""
    from datetime import date as date_type

    from app.schemas.market import IndexKlineItem, IndexKlineResponse

    query = db.query(IndexKline).filter(IndexKline.code == code)
    if start:
        query = query.filter(IndexKline.trade_date >= date_type.fromisoformat(start))
    if end:
        query = query.filter(IndexKline.trade_date <= date_type.fromisoformat(end))

    records = query.order_by(IndexKline.trade_date.asc()).all()

    # On-demand crawl if no data
    if not records:
        from app.services.crawler import crawl_index_kline
        cfg = {c["code"]: c for c in [
            {"code": "sh000001", "name": "上证指数"},
            {"code": "sz399001", "name": "深证成指"},
            {"code": "sz399006", "name": "创业板指"},
            {"code": "sh000688", "name": "科创50"},
            {"code": "sh000300", "name": "沪深300"},
        ]}
        info = cfg.get(code, {"name": code})
        crawl_index_kline(code, info["name"], db)
        records = query.order_by(IndexKline.trade_date.asc()).all()

    name = records[0].name if records else code
    data = [
        IndexKlineItem(
            date=r.trade_date.isoformat(), open=r.open, high=r.high,
            low=r.low, close=r.close, volume=r.volume, amount=r.amount,
        )
        for r in records
    ]
    return IndexKlineResponse(code=code, name=name, data=data)


@router.get("/turnover")
def get_turnover(
    days: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily total market turnover history."""
    from app.schemas.market import TurnoverItem, TurnoverResponse

    records = (
        db.query(MarketTurnover)
        .order_by(MarketTurnover.trade_date.desc())
        .limit(days)
        .all()
    )

    # On-demand crawl if no data
    if not records:
        from app.services.crawler import crawl_market_turnover
        crawl_market_turnover(db)
        records = (
            db.query(MarketTurnover)
            .order_by(MarketTurnover.trade_date.desc())
            .limit(days)
            .all()
        )

    data = [
        TurnoverItem(
            trade_date=r.trade_date.isoformat(),
            total_amount=r.total_amount,
            total_volume=r.total_volume,
            stock_count=r.stock_count,
        )
        for r in reversed(records)  # chronological order
    ]
    return TurnoverResponse(data=data)
