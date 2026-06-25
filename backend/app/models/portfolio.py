"""Portfolio, PortfolioHolding, and PortfolioNavHistory models."""
from datetime import date, datetime

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    return_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="portfolios")
    holdings = relationship(
        "PortfolioHolding", back_populates="portfolio", cascade="all, delete-orphan"
    )
    nav_history = relationship(
        "PortfolioNavHistory", back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Portfolio(code={self.code}, name={self.name})>"


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "stock_id", name="uk_portfolio_stock"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    cost_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_price_set_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    portfolio = relationship("Portfolio", back_populates="holdings")
    stock = relationship("Stock", back_populates="holdings")

    @property
    def is_cost_locked(self) -> bool:
        """Cost price is immutable once set."""
        return self.cost_price is not None

    def __repr__(self) -> str:
        return (
            f"<PortfolioHolding(portfolio_id={self.portfolio_id}, "
            f"stock_id={self.stock_id}, shares={self.shares})>"
        )


class PortfolioNavHistory(Base):
    __tablename__ = "portfolio_nav_history"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "nav_date", name="uk_portfolio_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    daily_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_return_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    cum_return_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationship
    portfolio = relationship("Portfolio", back_populates="nav_history")

    def __repr__(self) -> str:
        return f"<PortfolioNavHistory(portfolio_id={self.portfolio_id}, date={self.nav_date})>"
