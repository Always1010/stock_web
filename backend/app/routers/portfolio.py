"""Portfolio routes: CRUD, holdings, cost price, NAV, charts."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioNavHistory
from app.models.stock import DailyKline, Stock
from app.models.user import User
from app.schemas.portfolio import (
    AddHoldingRequest,
    ContributionItem,
    ContributionResponse,
    DailyReturnItem,
    DailyReturnsResponse,
    HoldingResponse,
    NavHistoryItem,
    NavHistoryResponse,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioSummary,
    PortfolioUpdate,
    SetCostPriceRequest,
    UpdateHoldingRequest,
)
from app.services.portfolio_service import (
    calculate_contributions,
    generate_portfolio_code,
    get_latest_close,
    set_holding_cost_price,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


# ── Portfolio CRUD ──────────────────────────────────────────────

@router.get("", response_model=list[PortfolioSummary])
def list_portfolios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's portfolios with latest NAV."""
    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id)
        .order_by(Portfolio.created_at.desc())
        .all()
    )

    result = []
    for p in portfolios:
        latest_nav = (
            db.query(PortfolioNavHistory)
            .filter(PortfolioNavHistory.portfolio_id == p.id)
            .order_by(PortfolioNavHistory.nav_date.desc())
            .first()
        )
        result.append(
            PortfolioSummary(
                code=p.code,
                name=p.name,
                created_at=p.created_at,
                latest_nav=latest_nav.nav if latest_nav else None,
                latest_return_rate=latest_nav.cum_return_rate if latest_nav else None,
            )
        )
    return result


@router.post("", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    req: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new portfolio."""
    code = generate_portfolio_code(db)
    portfolio = Portfolio(
        user_id=current_user.id,
        name=req.name,
        code=code,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    return PortfolioDetail(
        code=portfolio.code,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings=[],
        latest_nav=None,
        latest_return_rate=None,
    )


@router.get("/{code}", response_model=PortfolioDetail)
def get_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio detail with holdings."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    latest_nav = (
        db.query(PortfolioNavHistory)
        .filter(PortfolioNavHistory.portfolio_id == portfolio.id)
        .order_by(PortfolioNavHistory.nav_date.desc())
        .first()
    )

    holdings = []
    for h in portfolio.holdings:
        holdings.append(
            HoldingResponse(
                id=h.id,
                stock_code=h.stock.code,
                stock_name=h.stock.name,
                shares=h.shares,
                cost_price=h.cost_price,
                cost_price_set_at=h.cost_price_set_at,
                is_cost_locked=h.is_cost_locked,
            )
        )

    return PortfolioDetail(
        code=portfolio.code,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings=holdings,
        latest_nav=latest_nav.nav if latest_nav else None,
        latest_return_rate=latest_nav.cum_return_rate if latest_nav else None,
    )


@router.put("/{code}", response_model=PortfolioDetail)
def update_portfolio(
    code: str,
    req: PortfolioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update portfolio name."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    portfolio.name = req.name
    db.commit()
    db.refresh(portfolio)

    return get_portfolio(code, db, current_user)


@router.delete("/{code}", status_code=status.HTTP_200_OK)
def delete_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a portfolio and all related data."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    db.delete(portfolio)
    db.commit()

    return {"message": "Portfolio deleted", "code": code}


# ── Holdings ─────────────────────────────────────────────────────

@router.post("/{code}/holdings", status_code=status.HTTP_201_CREATED)
def add_holding(
    code: str,
    req: AddHoldingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a stock holding to a portfolio."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    stock = (
        db.query(Stock)
        .filter(Stock.code == req.stock_code, Stock.is_active == 1)
        .first()
    )
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    existing = (
        db.query(PortfolioHolding)
        .filter(
            PortfolioHolding.portfolio_id == portfolio.id,
            PortfolioHolding.stock_id == stock.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock already in portfolio. Use PUT to update shares.",
        )

    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        stock_id=stock.id,
        shares=req.shares,
    )

    # Set cost price
    set_holding_cost_price(holding, db, req.cost_price)

    db.add(holding)
    db.commit()
    db.refresh(holding)

    return {
        "id": holding.id,
        "stock_code": stock.code,
        "stock_name": stock.name,
        "shares": holding.shares,
        "cost_price": holding.cost_price,
        "cost_price_set_at": holding.cost_price_set_at,
        "is_cost_locked": holding.is_cost_locked,
    }


@router.put("/{code}/holdings/{holding_id}")
def update_holding(
    code: str,
    holding_id: int,
    req: UpdateHoldingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update holding shares (cost price remains unchanged)."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    holding = db.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == portfolio.id,
    ).first()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    holding.shares = req.shares
    db.commit()

    return {"message": "Holding updated", "id": holding.id, "shares": holding.shares}


@router.delete("/{code}/holdings/{holding_id}")
def remove_holding(
    code: str,
    holding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a holding from a portfolio."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    holding = db.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == portfolio.id,
    ).first()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    db.delete(holding)
    db.commit()

    return {"message": "Holding removed", "id": holding_id}


@router.post("/{code}/holdings/{holding_id}/set-cost")
def set_cost(
    code: str,
    holding_id: int,
    req: SetCostPriceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set or override cost price for a holding."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    holding = db.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == portfolio.id,
    ).first()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    if holding.is_cost_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cost price is immutable once set.",
        )

    holding.cost_price = req.cost_price
    holding.cost_price_set_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Cost price set",
        "cost_price": holding.cost_price,
    }


# ── Charts & Analytics ───────────────────────────────────────────

@router.get("/{code}/nav", response_model=NavHistoryResponse)
def get_nav_history(
    code: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get portfolio NAV history for return curve chart."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    query = db.query(PortfolioNavHistory).filter(
        PortfolioNavHistory.portfolio_id == portfolio.id
    )
    if start:
        query = query.filter(PortfolioNavHistory.nav_date >= date.fromisoformat(start))
    if end:
        query = query.filter(PortfolioNavHistory.nav_date <= date.fromisoformat(end))

    history = query.order_by(PortfolioNavHistory.nav_date.asc()).all()

    data = [
        NavHistoryItem(
            date=h.nav_date.isoformat(),
            nav=h.nav,
            daily_return=h.daily_return,
            daily_return_rate=h.daily_return_rate,
            cum_return_rate=h.cum_return_rate,
            total_cost=h.total_cost,
            total_market_value=h.total_market_value,
        )
        for h in history
    ]

    return NavHistoryResponse(
        portfolio_code=portfolio.code,
        portfolio_name=portfolio.name,
        data=data,
    )


@router.get("/{code}/daily-returns", response_model=DailyReturnsResponse)
def get_daily_returns(
    code: str,
    year: int = Query(..., description="Year for heatmap"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily returns for a specific year (for heatmap calendar)."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    history = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date >= start_date,
            PortfolioNavHistory.nav_date <= end_date,
        )
        .order_by(PortfolioNavHistory.nav_date.asc())
        .all()
    )

    data = [
        DailyReturnItem(
            date=h.nav_date.isoformat(),
            return_rate=h.daily_return_rate,
        )
        for h in history
    ]

    return DailyReturnsResponse(
        portfolio_code=portfolio.code,
        year=year,
        data=data,
    )


@router.get("/{code}/contributions", response_model=ContributionResponse)
def get_contributions(
    code: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get each stock's contribution to portfolio return for a date range."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None

    items = calculate_contributions(portfolio, db, start_date, end_date)

    return ContributionResponse(
        portfolio_code=portfolio.code,
        start_date=start or "",
        end_date=end or "",
        data=items,
    )
