"""Stock and DailyKline models."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(Enum("SH", "SZ", "BJ"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    daily_kline = relationship("DailyKline", back_populates="stock", cascade="all, delete-orphan")
    watchlist_items = relationship("WatchlistItem", back_populates="stock", cascade="all, delete-orphan")
    holdings = relationship("PortfolioHolding", back_populates="stock")

    def __repr__(self) -> str:
        return f"<Stock(code={self.code}, name={self.name})>"


class DailyKline(Base):
    __tablename__ = "daily_kline"
    __table_args__ = (
        UniqueConstraint("stock_id", "trade_date", name="uk_stock_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationship
    stock = relationship("Stock", back_populates="daily_kline")

    def __repr__(self) -> str:
        return f"<DailyKline(stock_id={self.stock_id}, date={self.trade_date})>"
