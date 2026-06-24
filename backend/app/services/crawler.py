"""Stock data crawler using Sina Finance API."""
import logging
import time
from datetime import date, datetime

import requests
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.crawl import CrawlLog
from app.models.stock import DailyKline, Stock

logger = logging.getLogger(__name__)

# ── Sina Finance API endpoints ──────────────────────────────
SINA_STOCK_LIST = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
SINA_KLINE = (
    "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "CN_MarketData.getKLineData"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _http_get_json(url: str, params: dict, timeout: int = 15, retries: int = 3) -> list | dict:
    """
    HTTP GET with retry, returning parsed JSON.
    Sina API returns a JSON list (stock list) or list of dicts (K-line).
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            # Sina API returns JSON with Content-Type: text/html
            text = resp.text.strip()
            if not text:
                raise ValueError("Empty response")
            import json
            return json.loads(text)
        except requests.exceptions.ConnectionError as e:
            last_exc = e
            logger.warning(f"Connection error on attempt {attempt}/{retries}: {e}")
        except requests.exceptions.Timeout as e:
            last_exc = e
            logger.warning(f"Timeout on attempt {attempt}/{retries}: {e}")
        except Exception as e:
            last_exc = e
            logger.warning(f"Error on attempt {attempt}/{retries}: {e}")

        if attempt < retries:
            time.sleep(2 ** attempt)

    raise last_exc  # type: ignore


def _determine_exchange(code: str) -> str | None:
    """Determine exchange from stock code prefix."""
    if code.startswith("6"):
        return "SH"
    elif code.startswith(("0", "3")):
        return "SZ"
    elif code.startswith(("8", "4")):
        return "BJ"
    return None


def _sina_symbol(code: str) -> str:
    """Convert stock code to Sina symbol: sh600519, sz000001, bj830799"""
    ex = _determine_exchange(code)
    return f"{ex.lower()}{code}"


# ═══════════════════════════════════════════════════════════
# Stock List
# ═══════════════════════════════════════════════════════════

def crawl_stock_list(db: Session | None = None) -> dict:
    """
    Crawl A-share stock list from Sina Finance.
    Fetches all pages, upserts into stocks table.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        logger.info("Starting stock list crawl (Sina Finance)...")

        all_stocks = []
        page = 1
        page_size = 100

        while True:
            params = {
                "page": page,
                "num": page_size,
                "sort": "symbol",
                "asc": 1,
                "node": "hs_a",       # A-share market
                "symbol": "",
                "_s_r_a": "init",
            }
            data = _http_get_json(SINA_STOCK_LIST, params)
            if not isinstance(data, list) or len(data) == 0:
                break

            for item in data:
                code = item.get("code", "")
                name = item.get("name", "")
                exchange = _determine_exchange(code)
                if code and name and exchange:
                    # Also capture latest price from the list response
                    all_stocks.append({"code": code, "name": name, "exchange": exchange})

            if len(data) < page_size:
                break
            page += 1
            time.sleep(0.3)

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

        logger.info(
            f"Stock list crawl done: added={added}, updated={updated}, total={len(all_stocks)}"
        )
        return {"added": added, "updated": updated, "total": len(all_stocks)}

    except Exception as e:
        logger.error(f"Stock list crawl failed: {e}")
        try:
            if close_db:
                log = CrawlLog(
                    crawl_type="stock_list",
                    ref_date=date.today(),
                    status="failed",
                    details={"error": str(e)},
                )
                db.add(log)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        if close_db and db:
            db.close()


# ═══════════════════════════════════════════════════════════
# K-line
# ═══════════════════════════════════════════════════════════

def crawl_kline_for_stock(stock: Stock, db: Session, datalen: int = 400) -> int:
    """
    Crawl daily K-line for one stock from Sina Finance.
    Returns number of new records inserted.
    """
    params = {
        "symbol": _sina_symbol(stock.code),
        "scale": "240",        # daily
        "ma": "no",            # no MA (we calculate in frontend)
        "datalen": str(datalen),
    }

    try:
        data = _http_get_json(SINA_KLINE, params)
        if not isinstance(data, list) or len(data) == 0:
            return 0

        inserted = 0
        for item in data:
            trade_date_str = item.get("day", "")
            if len(trade_date_str) == 8:
                trade_date = date(
                    int(trade_date_str[:4]),
                    int(trade_date_str[4:6]),
                    int(trade_date_str[6:8]),
                )
            elif "-" in trade_date_str:
                trade_date = date.fromisoformat(trade_date_str)
            else:
                continue

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
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=int(item["volume"]),
                amount=float(item.get("amount", 0) or 0),
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
    """Fetch K-line on demand, then return all records for this stock."""
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
    Crawl K-line for all active stocks. Rate-limited ~2 req/sec.
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
                        f"K-line: {i+1}/{len(stocks)} stocks, {total_inserted} records"
                    )
            except Exception as e:
                errors += 1
                logger.error(f"Error {stock.code}: {e}")

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
