"""Watchlist routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import DailyKline, Stock
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import WatchlistItemResponse, WatchlistListResponse
from app.utils.security import get_current_user

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def _get_latest_close(stock_id: int, db: Session) -> float | None:
    """Get the most recent close price for a stock."""
    k = (
        db.query(DailyKline)
        .filter(DailyKline.stock_id == stock_id)
        .order_by(DailyKline.trade_date.desc())
        .first()
    )
    return k.close if k else None


@router.get("", response_model=WatchlistListResponse)
def get_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's watchlist."""
    items = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == current_user.id)
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )

    result = []
    for item in items:
        stock = item.stock
        latest_close = _get_latest_close(stock.id, db)
        result.append(
            WatchlistItemResponse(
                id=item.id,
                code=stock.code,
                name=stock.name,
                exchange=stock.exchange,
                latest_close=latest_close,
                added_at=item.added_at,
            )
        )

    return WatchlistListResponse(items=result)


@router.post("/{code}", status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a stock to the watchlist."""
    stock = db.query(Stock).filter(Stock.code == code, Stock.is_active == 1).first()
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    existing = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.stock_id == stock.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in watchlist")

    item = WatchlistItem(user_id=current_user.id, stock_id=stock.id)
    db.add(item)
    db.commit()

    return {"message": "Added to watchlist", "code": code}


@router.delete("/{code}", status_code=status.HTTP_200_OK)
def remove_from_watchlist(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a stock from the watchlist."""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    item = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == current_user.id,
            WatchlistItem.stock_id == stock.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in watchlist")

    db.delete(item)
    db.commit()

    return {"message": "Removed from watchlist", "code": code}
