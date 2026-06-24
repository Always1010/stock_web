"""Market index, breadth, and sector models."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketIndex(Base):
    """Daily snapshot of major A-share indices."""
    __tablename__ = "market_index"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uk_idx_code_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    change: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<MarketIndex(code={self.code}, date={self.trade_date}, close={self.close})>"


class MarketBreadth(Base):
    """Daily market breadth: up/down/flat counts for major boards."""
    __tablename__ = "market_breadth"
    __table_args__ = (
        UniqueConstraint("board", "trade_date", name="uk_breadth_board_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # 'SH'/'SZ'/'ALL'
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<MarketBreadth(board={self.board}, date={self.trade_date}, up={self.up_count})>"


class SectorData(Base):
    """Daily sector/板块 performance ranking."""
    __tablename__ = "sector_data"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uk_sector_code_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    leading_stock: Mapped[str | None] = mapped_column(String(64), nullable=True)
    leading_stock_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<SectorData(name={self.name}, date={self.trade_date}, pct={self.change_pct})>"


class IndexKline(Base):
    """Historical daily K-line data for market indices."""
    __tablename__ = "index_kline"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uk_idx_kline_code_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<IndexKline(code={self.code}, date={self.trade_date})>"
