"""Stock data crawler using East Money API directly."""
import json
import logging
import time
from datetime import date, datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.crawl import CrawlLog
from app.models.stock import DailyKline, Stock

logger = logging.getLogger(__name__)

# East Money API endpoints
EM_LIST_URL = "http://82.push2.eastmoney.com/api/qt/clist/get"
EM_KLINE_URL = "http://82.push2his.eastmoney.com/api/qt/stock/kline/get"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://quote.eastmoney.com/",
}


def _create_session() -> requests.Session:
    """Create a requests session with retry logic."""
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def _determine_exchange(code: str) -> str | None:
    """Determine exchange from stock code prefix."""
    if code.startswith("6"):
        return "SH"
    elif code.startswith(("0", "3")):
        return "SZ"
    elif code.startswith(("8", "4")):
        return "BJ"
    return None


def _em_market_code(code: str) -> str:
    """Convert stock code to East Money market code."""
    exchange = _determine_exchange(code)
    if exchange == "SH":
        return f"1.{code}"
    elif exchange == "SZ":
        return f"0.{code}"
    elif exchange == "BJ":
        return f"0.{code}"
    return f"0.{code}"


def crawl_stock_list(db: Session | None = None) -> dict:
    """
    Crawl A-share stock list from East Money API.
    Upserts into stocks table. Returns summary dict.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        logger.info("Starting stock list crawl...")

        all_stocks = []
        page = 1
        page_size = 500

        while True:
            params = {
                "pn": str(page),
                "pz": str(page_size),
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                "fields": "f12,f14",
            }
            resp = requests.get(EM_LIST_URL, params=params, headers=HEADERS, timeout=15)
            data = resp.json()
            diff = data.get("data", {}).get("diff", [])
            if not diff:
                break

            for item in diff:
                code = item.get("f12", "")
                name = item.get("f14", "")
                exchange = _determine_exchange(code)
                if code and name and exchange:
                    all_stocks.append({"code": code, "name": name, "exchange": exchange})

            total = data.get("data", {}).get("total", 0)
            if page * page_size >= total:
                break
            page += 1
            time.sleep(0.2)

        added = 0
        updated = 0
        for s in all_stocks:
            existing = db.query(Stock).filter(Stock.code == s["code"]).first()
            if existing:
                if existing.name != s["name"]:
                    existing.name = s["name"]
                    existing.updated_at = datetime.utcnow()
                    updated += 1
            else:
                stock = Stock(
                    code=s["code"], exchange=s["exchange"], name=s["name"], is_active=1
                )
                db.add(stock)
                added += 1

        db.commit()

        log = CrawlLog(
            crawl_type="stock_list",
            ref_date=date.today(),
            status="success",
            details={"added": added, "updated": updated, "total": len(all_stocks)},
        )
        db.add(log)
        db.commit()

        logger.info(f"Stock list crawl done: added={added}, updated={updated}, total={len(all_stocks)}")
        return {"added": added, "updated": updated, "total": len(all_stocks)}

    except Exception as e:
        logger.error(f"Stock list crawl failed: {e}")
        try:
            log = CrawlLog(
                crawl_type="stock_list",
                ref_date=date.today(),
                status="failed",
                details={"error": str(e)},
            )
            if close_db:
                db.add(log)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        if close_db and db:
            db.close()


def crawl_kline_for_stock(stock: Stock, db: Session, days: int = 365) -> int:
    """
    Crawl daily K-line data for a single stock from East Money API.
    Returns number of new records inserted.
    """
    market_code = _em_market_code(stock.code)
    params = {
        "secid": market_code,
        "klt": "101",  # Daily K-line
        "fqt": "1",    # Forward-adjusted (前复权)
        "beg": "20240101",
        "end": date.today().strftime("%Y%m%d"),
        "lmt": str(days),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }

    try:
        resp = requests.get(EM_KLINE_URL, params=params, headers=HEADERS, timeout=15)
        data = resp.json()

        klines_raw = data.get("data", {}).get("klines", [])
        if not klines_raw:
            return 0

        inserted = 0
        for line in klines_raw:
            parts = line.split(",")
            if len(parts) < 7:
                continue

            # Format: date,open,close,high,low,volume,amount
            trade_date_str = parts[0]
            if len(trade_date_str) == 8:
                trade_date = date(
                    int(trade_date_str[:4]),
                    int(trade_date_str[4:6]),
                    int(trade_date_str[6:8]),
                )
            else:
                trade_date = date.fromisoformat(trade_date_str)

            # Check if already exists
            existing = (
                db.query(DailyKline)
                .filter(
                    DailyKline.stock_id == stock.id,
                    DailyKline.trade_date == trade_date,
                )
                .first()
            )
            if existing:
                continue

            kline = DailyKline(
                stock_id=stock.id,
                trade_date=trade_date,
                open=float(parts[1]),
                close=float(parts[2]),
                high=float(parts[3]),
                low=float(parts[4]),
                volume=int(parts[5]),
                amount=float(parts[6]),
            )
            db.add(kline)
            inserted += 1

        db.commit()
        return inserted

    except Exception as e:
        logger.warning(f"Failed to crawl K-line for {stock.code}: {e}")
        return 0


def crawl_kline_on_demand(
    stock: Stock, db: Session, start: str | None = None, end: str | None = None
) -> list[DailyKline]:
    """Fetch K-line data on demand for a stock, then return all records."""
    count = crawl_kline_for_stock(stock, db)
    if count > 0:
        logger.info(f"On-demand crawl for {stock.code}: {count} records")
    return (
        db.query(DailyKline)
        .filter(DailyKline.stock_id == stock.id)
        .order_by(DailyKline.trade_date.asc())
        .all()
    )


def crawl_all_kline(db: Session | None = None, limit: int | None = None) -> dict:
    """
    Crawl K-line data for all active stocks.
    Rate-limited to ~2 requests/second.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        stocks = db.query(Stock).filter(Stock.is_active == 1).all()
        if limit:
            stocks = stocks[:limit]

        total_inserted = 0
        errors = 0

        for i, stock in enumerate(stocks):
            try:
                inserted = crawl_kline_for_stock(stock, db)
                total_inserted += inserted
                if (i + 1) % 20 == 0:
                    logger.info(
                        f"Crawled K-line: {i+1}/{len(stocks)} stocks, {total_inserted} records"
                    )
            except Exception as e:
                errors += 1
                logger.error(f"Error crawling {stock.code}: {e}")

            # Rate limit: ~2 req/sec
            time.sleep(0.5)

        log = CrawlLog(
            crawl_type="daily_kline",
            ref_date=date.today(),
            status="success" if errors == 0 else "partial",
            details={
                "stocks_processed": len(stocks),
                "records_inserted": total_inserted,
                "errors": errors,
            },
        )
        db.add(log)
        db.commit()

        return {"stocks": len(stocks), "inserted": total_inserted, "errors": errors}

    finally:
        if close_db and db:
            db.close()
