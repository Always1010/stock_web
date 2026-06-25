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
    MonthlyReturnItem,
    MonthlyReturnsResponse,
    NavHistoryItem,
    NavHistoryResponse,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioNavRecalcResponse,
    PortfolioRefreshResponse,
    PortfolioSummary,
    PortfolioUpdate,
    SetCostPriceRequest,
    SetReturnStartDateRequest,
    UpdateHoldingRequest,
)
from app.services.portfolio_service import (
    calculate_contributions,
    fill_missing_nav,
    generate_portfolio_code,
    get_latest_close,
    recalculate_portfolio_nav,
    refresh_portfolio_kline,
    set_holding_cost_price,
)
from app.utils.security import get_current_user

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


def _get_user_portfolio(
    code: str, db: Session, current_user: User
) -> Portfolio:
    """Look up a portfolio by code, ensuring it belongs to the current user."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found"
        )
    return portfolio


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
        cum_return = None
        if latest_nav and latest_nav.total_cost and latest_nav.total_cost > 0:
            cum_return = latest_nav.total_market_value - latest_nav.total_cost
        result.append(
            PortfolioSummary(
                code=p.code,
                name=p.name,
                created_at=p.created_at,
                return_start_date=p.return_start_date,
                latest_nav=latest_nav.nav if latest_nav else None,
                latest_cumulative_return=cum_return,
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
        return_start_date=portfolio.return_start_date,
        holdings=[],
        latest_nav=None,
        latest_cumulative_return=None,
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

    cum_return = None
    if latest_nav and latest_nav.total_cost and latest_nav.total_cost > 0:
        cum_return = latest_nav.total_market_value - latest_nav.total_cost

    holdings = []
    for h in portfolio.holdings:
        current_price = get_latest_close(h.stock_id, db)
        return_amount = None
        return_rate = None
        if h.cost_price is not None and current_price is not None and h.cost_price > 0:
            return_amount = (current_price - h.cost_price) * h.shares
            return_rate = (current_price / h.cost_price) - 1
        holdings.append(
            HoldingResponse(
                id=h.id,
                stock_code=h.stock.code,
                stock_name=h.stock.name,
                shares=h.shares,
                cost_price=h.cost_price,
                cost_price_set_at=h.cost_price_set_at,
                is_cost_locked=h.is_cost_locked,
                current_price=current_price,
                return_amount=return_amount,
                return_rate=return_rate,
            )
        )

    return PortfolioDetail(
        code=portfolio.code,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        return_start_date=portfolio.return_start_date,
        holdings=holdings,
        latest_nav=latest_nav.nav if latest_nav else None,
        latest_cumulative_return=cum_return,
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
    year: int = Query(..., description="Year for calendar"),
    month: int | None = Query(None, description="Optional month filter (1-12)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily returns for a specific year/month (for calendar)."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    if month is not None:
        import calendar
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
    else:
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
            return_amount=h.daily_return,
            return_rate=h.daily_return_rate,
        )
        for h in history
    ]

    return DailyReturnsResponse(
        portfolio_code=portfolio.code,
        year=year,
        month=month,
        data=data,
    )


@router.get("/{code}/monthly-returns", response_model=MonthlyReturnsResponse)
def get_monthly_returns(
    code: str,
    year: int = Query(..., description="Year for monthly aggregation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated monthly returns for a year."""
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    import calendar as cal_mod

    data = []
    for month in range(1, 13):
        last_day = cal_mod.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        month_navs = (
            db.query(PortfolioNavHistory)
            .filter(
                PortfolioNavHistory.portfolio_id == portfolio.id,
                PortfolioNavHistory.nav_date >= start_date,
                PortfolioNavHistory.nav_date <= end_date,
            )
            .order_by(PortfolioNavHistory.nav_date.asc())
            .all()
        )

        return_amount = None
        return_rate = None

        if month_navs:
            # Sum daily returns for the month
            daily_amounts = [n.daily_return for n in month_navs if n.daily_return is not None]
            if daily_amounts:
                return_amount = sum(daily_amounts)

            # Use the cumulative return rate at the last trading day
            last_record = month_navs[-1]
            return_rate = last_record.cum_return_rate

        data.append(
            MonthlyReturnItem(
                month=month,
                return_amount=return_amount,
                return_rate=return_rate,
            )
        )

    return MonthlyReturnsResponse(
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


# ── Return Start Date ────────────────────────────────────────────

@router.put("/{code}/return-start-date", response_model=PortfolioDetail)
def set_return_start_date(
    code: str,
    req: SetReturnStartDateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the return calculation start date for a portfolio."""
    portfolio = _get_user_portfolio(code, db, current_user)
    portfolio.return_start_date = req.return_start_date
    db.commit()
    db.refresh(portfolio)
    return get_portfolio(code, db, current_user)


# ── Portfolio Data Refresh ───────────────────────────────────────

@router.post("/{code}/refresh-data", response_model=PortfolioRefreshResponse)
def refresh_portfolio_data_full(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full data refresh: re-crawl all holdings' kline data (overwrite=True)."""
    portfolio = _get_user_portfolio(code, db, current_user)
    result = refresh_portfolio_kline(portfolio, db, overwrite=True)
    result["message"] = (
        f"全量更新完成: 处理 {result['processed']}/{result['total_stocks']} 只股票, "
        f"更新 {result['total_affected']} 条记录"
    )
    return result


@router.post("/{code}/refresh-data/incr", response_model=PortfolioRefreshResponse)
def refresh_portfolio_data_incr(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Incremental data refresh: crawl only missing kline data (overwrite=False)."""
    portfolio = _get_user_portfolio(code, db, current_user)
    result = refresh_portfolio_kline(portfolio, db, overwrite=False)
    result["message"] = (
        f"增量更新完成: 处理 {result['processed']}/{result['total_stocks']} 只股票, "
        f"新增 {result['total_affected']} 条记录"
    )
    return result


# ── Portfolio NAV Recalculation ──────────────────────────────────

@router.post("/{code}/recalc-nav", response_model=PortfolioNavRecalcResponse)
def recalc_portfolio_nav_full(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full NAV recalculation: delete NAV from return_start_date and recompute."""
    portfolio = _get_user_portfolio(code, db, current_user)
    result = recalculate_portfolio_nav(portfolio, db)
    result["message"] = f"全量收益计算完成: 生成 {result['records_created']} 条收益记录"
    return result


@router.post("/{code}/recalc-nav/incr", response_model=PortfolioNavRecalcResponse)
def recalc_portfolio_nav_incr(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Incremental NAV fill: find latest NAV date and fill missing days to today."""
    portfolio = _get_user_portfolio(code, db, current_user)
    result = fill_missing_nav(portfolio, db)
    result["message"] = f"增量收益计算完成: 生成 {result['records_created']} 条收益记录"
    return result
