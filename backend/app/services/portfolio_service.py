"""Portfolio business logic: NAV calculation, cost price, contributions."""
import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioNavHistory
from app.models.stock import DailyKline
from app.schemas.portfolio import ContributionItem
from app.utils.date_utils import is_after_3pm, now_cst, today_cst

logger = logging.getLogger(__name__)


# ── Portfolio Code Generation ────────────────────────────────────

def generate_portfolio_code(db: Session) -> str:
    """Generate a unique portfolio code: PF{YYYYMMDD}{NNN}"""
    today_str = today_cst().strftime("%Y%m%d")
    prefix = f"PF{today_str}"

    last = (
        db.query(Portfolio)
        .filter(Portfolio.code.like(f"{prefix}%"))
        .order_by(Portfolio.code.desc())
        .first()
    )

    if last:
        last_seq = int(last.code[-3:])
        new_seq = last_seq + 1
    else:
        new_seq = 1

    return f"{prefix}{new_seq:03d}"


# ── Cost Price Logic ─────────────────────────────────────────────

def get_latest_close(stock_id: int, db: Session, before_date: date | None = None) -> float | None:
    """Get the most recent close price for a stock, optionally before a date."""
    query = db.query(DailyKline).filter(DailyKline.stock_id == stock_id)
    if before_date:
        query = query.filter(DailyKline.trade_date < before_date)
    kline = query.order_by(DailyKline.trade_date.desc()).first()
    return kline.close if kline else None


def set_holding_cost_price(
    holding: PortfolioHolding,
    db: Session,
    user_provided_cost: float | None = None,
) -> PortfolioHolding:
    """
    Determine and set the cost price for a holding.

    Rules:
    1. If user provides cost_price → use it immediately, lock.
    2. If no cost provided and before 3 PM CST → use previous trading day close.
    3. If no cost provided and after 3 PM CST → use today's close (fallback to previous).
    4. Once set, cost_price is immutable (enforced at call site).

    Returns the holding with cost_price set (or still None if no data available).
    """
    if holding.is_cost_locked:
        return holding  # Already set, no change

    if user_provided_cost is not None:
        holding.cost_price = user_provided_cost
        holding.cost_price_set_at = datetime.utcnow()
        return holding

    # Default logic based on time of day
    today = today_cst()

    if is_after_3pm():
        # After 3 PM: try today's close first
        today_close = get_latest_close(holding.stock_id, db, before_date=None)
        # Check if the latest close is actually from today
        today_kline = (
            db.query(DailyKline)
            .filter(
                DailyKline.stock_id == holding.stock_id,
                DailyKline.trade_date == today,
            )
            .first()
        )
        if today_kline:
            holding.cost_price = today_kline.close
        elif today_close is not None:
            # Weekend/holiday: use most recent trading day
            holding.cost_price = today_close
    else:
        # Before 3 PM: use previous trading day's close
        prev_close = get_latest_close(holding.stock_id, db, before_date=today)
        if prev_close is not None:
            holding.cost_price = prev_close

    if holding.cost_price is not None:
        holding.cost_price_set_at = datetime.utcnow()

    return holding


# ── NAV Calculation ──────────────────────────────────────────────

def update_portfolio_nav(portfolio: Portfolio, db: Session) -> PortfolioNavHistory | None:
    """
    Calculate and record today's NAV for a portfolio.
    Returns the new PortfolioNavHistory record, or None if no data available.
    """
    today = today_cst()

    total_market_value = 0.0
    total_cost = 0.0

    for holding in portfolio.holdings:
        # Get today's close (or latest available)
        close = get_latest_close(holding.stock_id, db)
        if close is None:
            logger.warning(
                f"No price data for stock {holding.stock.code} in portfolio {portfolio.code}"
            )
            continue

        market_value = holding.shares * close
        total_market_value += market_value

        if holding.cost_price is not None:
            total_cost += holding.shares * holding.cost_price

    # Get yesterday's NAV for daily return calculation
    yesterday_nav = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date < today,
        )
        .order_by(PortfolioNavHistory.nav_date.desc())
        .first()
    )

    # Calculate returns
    daily_return = None
    daily_return_rate = None
    if yesterday_nav and yesterday_nav.nav > 0:
        daily_return = total_market_value - yesterday_nav.nav
        daily_return_rate = daily_return / yesterday_nav.nav

    cum_return_rate = None
    if total_cost > 0:
        cum_return_rate = (total_market_value / total_cost) - 1

    # Check if today's NAV already exists (upsert)
    existing = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date == today,
        )
        .first()
    )

    if existing:
        existing.nav = total_market_value
        existing.daily_return = daily_return
        existing.daily_return_rate = daily_return_rate
        existing.cum_return_rate = cum_return_rate
        existing.total_cost = total_cost
        existing.total_market_value = total_market_value
        db.commit()
        return existing

    nav_record = PortfolioNavHistory(
        portfolio_id=portfolio.id,
        nav_date=today,
        nav=total_market_value,
        daily_return=daily_return,
        daily_return_rate=daily_return_rate,
        cum_return_rate=cum_return_rate,
        total_cost=total_cost,
        total_market_value=total_market_value,
    )
    db.add(nav_record)
    db.commit()
    return nav_record


def update_all_portfolios_nav(db: Session | None = None) -> dict:
    """Update NAV for all portfolios. Called by scheduler at 15:05 daily."""
    from app.database import SessionLocal

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        portfolios = db.query(Portfolio).all()
        updated = 0
        errors = 0

        for portfolio in portfolios:
            try:
                result = update_portfolio_nav(portfolio, db)
                if result:
                    updated += 1
            except Exception as e:
                errors += 1
                logger.error(f"NAV update failed for {portfolio.code}: {e}")

        logger.info(f"NAV update done: {updated} portfolios, {errors} errors")
        return {"updated": updated, "errors": errors}

    finally:
        if close_db and db:
            db.close()


# ── Contribution Analysis ────────────────────────────────────────

def calculate_contributions(
    portfolio: Portfolio,
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ContributionItem]:
    """
    Calculate each holding's contribution to portfolio return.
    If start_date and end_date are not provided, uses all available history.
    """
    items = []

    for holding in portfolio.holdings:
        stock = holding.stock

        # Get price at start and end of period
        start_kline = None
        end_kline = None

        kline_query = db.query(DailyKline).filter(DailyKline.stock_id == stock.id)

        if start_date:
            start_kline = (
                kline_query.filter(DailyKline.trade_date >= start_date)
                .order_by(DailyKline.trade_date.asc())
                .first()
            )
        else:
            # First available kline
            start_kline = kline_query.order_by(DailyKline.trade_date.asc()).first()

        if end_date:
            end_kline = (
                kline_query.filter(DailyKline.trade_date <= end_date)
                .order_by(DailyKline.trade_date.desc())
                .first()
            )
        else:
            # Last available kline
            end_kline = kline_query.order_by(DailyKline.trade_date.desc()).first()

        start_price = start_kline.close if start_kline else None
        end_price = end_kline.close if end_kline else None

        market_value = holding.shares * end_price if end_price else 0.0

        return_amount = None
        return_rate = None
        contribution_pct = None

        if holding.cost_price is not None and end_price is not None:
            return_amount = (end_price - holding.cost_price) * holding.shares
            return_rate = (end_price / holding.cost_price) - 1

            # Contribution as percentage of portfolio total cost
            total_cost = sum(
                h.shares * h.cost_price
                for h in portfolio.holdings
                if h.cost_price is not None
            )
            if total_cost > 0:
                contribution_pct = return_amount / total_cost

        items.append(
            ContributionItem(
                stock_code=stock.code,
                stock_name=stock.name,
                shares=holding.shares,
                cost_price=holding.cost_price,
                start_price=start_price,
                end_price=end_price,
                market_value=market_value,
                return_amount=return_amount,
                return_rate=return_rate,
                contribution_pct=contribution_pct,
            )
        )

    return items
