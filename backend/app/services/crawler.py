"""Stock data crawler using Sina Finance API."""
import json
import logging
import re
import time
from datetime import date, datetime

import requests
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.crawl import CrawlLog
from app.models.market import IndexKline, MarketBreadth, MarketIndex, MarketTurnover, SectorData
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

# datalen strategy: full history (10000 ≈ all available, verified up to 8378 records / 1991)
FULL_DATALEN = 10000
# incremental buffer: 10 days covers weekends + long holidays
INCR_DATALEN = 10

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
    elif code.startswith(("8", "4", "92")):
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

def _parse_date(date_str: str) -> date | None:
    """Parse date from Sina K-line API response. Supports 'YYYYMMDD' and 'YYYY-MM-DD'."""
    if not date_str:
        return None
    if len(date_str) == 8:
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    elif "-" in date_str:
        return date.fromisoformat(date_str)
    return None


def _get_stock_latest_date(stock_id: int, db: Session) -> date | None:
    """Return the latest trade_date in DailyKline for a given stock, or None."""
    from sqlalchemy import func as sqla_func

    return (
        db.query(sqla_func.max(DailyKline.trade_date))
        .filter(DailyKline.stock_id == stock_id)
        .scalar()
    )


def crawl_kline_for_stock(
    stock: Stock, db: Session, datalen: int = FULL_DATALEN, overwrite: bool = False
) -> int:
    """
    Crawl daily K-line for one stock from Sina Finance.

    When overwrite=False (default): insert only missing dates, returns new records count.
    When overwrite=True: upsert all fetched data (insert new + update existing), returns total affected.
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

        # Parse API data into {trade_date: item} dict
        new_records: dict[date, dict] = {}
        for item in data:
            trade_date = _parse_date(item.get("day", ""))
            if trade_date:
                new_records[trade_date] = item

        if not new_records:
            return 0

        if overwrite:
            # ── Overwrite mode: batch-fetch existing rows, upsert ──
            dates_list = list(new_records.keys())
            existing_map: dict[date, DailyKline] = {}
            chunk_size = 500
            for i in range(0, len(dates_list), chunk_size):
                chunk = dates_list[i : i + chunk_size]
                rows = (
                    db.query(DailyKline)
                    .filter(
                        DailyKline.stock_id == stock.id,
                        DailyKline.trade_date.in_(chunk),
                    )
                    .all()
                )
                for r in rows:
                    existing_map[r.trade_date] = r

            affected = 0
            for trade_date in sorted(new_records):
                item = new_records[trade_date]
                close = float(item["close"])
                volume = int(item["volume"])
                amount = float(item.get("amount", 0) or 0) or (close * volume)

                if trade_date in existing_map:
                    row = existing_map[trade_date]
                    row.open = float(item["open"])
                    row.high = float(item["high"])
                    row.low = float(item["low"])
                    row.close = close
                    row.volume = volume
                    row.amount = amount
                else:
                    db.add(DailyKline(
                        stock_id=stock.id,
                        trade_date=trade_date,
                        open=float(item["open"]),
                        high=float(item["high"]),
                        low=float(item["low"]),
                        close=close,
                        volume=volume,
                        amount=amount,
                    ))
                affected += 1

            if affected > 0:
                db.commit()
            return affected

        else:
            # ── Insert-only mode (default) ──
            existing_dates: set[date] = set()
            dates_list = list(new_records.keys())
            chunk_size = 500
            for i in range(0, len(dates_list), chunk_size):
                chunk = dates_list[i : i + chunk_size]
                rows = (
                    db.query(DailyKline.trade_date)
                    .filter(
                        DailyKline.stock_id == stock.id,
                        DailyKline.trade_date.in_(chunk),
                    )
                    .all()
                )
                existing_dates.update(r[0] for r in rows)

            inserted = 0
            for trade_date in sorted(new_records):
                if trade_date in existing_dates:
                    continue
                item = new_records[trade_date]
                close = float(item["close"])
                volume = int(item["volume"])
                amount = float(item.get("amount", 0) or 0) or (close * volume)
                kline = DailyKline(
                    stock_id=stock.id,
                    trade_date=trade_date,
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=close,
                    volume=volume,
                    amount=amount,
                )
                db.add(kline)
                inserted += 1

            if inserted > 0:
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

    Smart datalen strategy per stock:
      - No existing data → FULL_DATALEN (first-time full history)
      - Already latest    → skip (no API call)
      - Has gap           → gap_days + INCR_DATALEN (incremental)
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        stocks = db.query(Stock).filter(Stock.is_active == 1).all()
        if limit:
            stocks = stocks[:limit]

        # Latest date across ALL stocks in DB (market-level benchmark)
        from sqlalchemy import func as sqla_func

        latest_market_date = (
            db.query(sqla_func.max(DailyKline.trade_date)).scalar()
        )
        today = date.today()

        total_inserted = 0
        total_skipped = 0
        errors = 0

        for i, stock in enumerate(stocks):
            try:
                latest = _get_stock_latest_date(stock.id, db)

                if latest is not None and latest_market_date is not None and latest >= latest_market_date:
                    total_skipped += 1
                else:
                    if latest is None:
                        datalen = FULL_DATALEN
                    else:
                        gap = (today - latest).days + INCR_DATALEN
                        datalen = min(gap, FULL_DATALEN)

                    inserted = crawl_kline_for_stock(stock, db, datalen=datalen)
                    total_inserted += inserted
                    time.sleep(0.5)  # rate-limit only when making API calls

            except Exception as e:
                errors += 1
                logger.error(f"Error {stock.code}: {e}")

            if (i + 1) % 50 == 0:
                logger.info(
                    f"K-line: {i+1}/{len(stocks)} stocks, "
                    f"{total_inserted} inserted, {total_skipped} skipped, {errors} errors"
                )

        log = CrawlLog(
            crawl_type="daily_kline",
            ref_date=date.today(),
            status="success" if errors == 0 else "partial",
            details={
                "stocks_processed": len(stocks),
                "records_inserted": total_inserted,
                "stocks_skipped": total_skipped,
                "errors": errors,
            },
        )
        db.add(log)
        db.commit()

        return {
            "stocks": len(stocks),
            "inserted": total_inserted,
            "skipped": total_skipped,
            "errors": errors,
        }

    finally:
        if close_db and db:
            db.close()


# ═══════════════════════════════════════════════════════════
# Market Indices (Sina real-time)
# ═══════════════════════════════════════════════════════════

INDEX_CONFIG = [
    {"code": "sh000001", "name": "上证指数", "board": "SH"},
    {"code": "sz399001", "name": "深证成指", "board": "SZ"},
    {"code": "sz399006", "name": "创业板指", "board": "SZ"},
    {"code": "sh000688", "name": "科创50", "board": "SH"},
    {"code": "sh000300", "name": "沪深300", "board": "SH"},
]

SINA_REALTIME_URL = "http://hq.sinajs.cn/list="


def _fetch_sina_realtime(symbols: list[str]) -> dict[str, dict]:
    """Fetch real-time quotes from Sina for given symbols."""
    url = SINA_REALTIME_URL + ",".join(symbols)
    headers = {**HEADERS, "Referer": "http://finance.sina.com.cn/"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.encoding = "gbk"
    results = {}
    for line in resp.text.strip().split("\n"):
        match = re.match(r'var hq_str_(\w+)="(.+)"', line.strip())
        if not match:
            continue
        sym = match.group(1)
        values = match.group(2).split(",")
        results[sym] = values
    return results


def crawl_market_indices(db: Session | None = None) -> dict:
    """Crawl major A-share indices and store in market_index."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        today = date.today()
        data = _fetch_sina_realtime([c["code"] for c in INDEX_CONFIG])
        inserted = 0
        for cfg in INDEX_CONFIG:
            key = cfg["code"]
            if key not in data or len(data[key]) < 6:
                continue
            vals = data[key]
            open_p = float(vals[1])
            prev_close = float(vals[2])
            current = float(vals[3])
            high = float(vals[4])
            low = float(vals[5])
            change = current - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            existing = (
                db.query(MarketIndex)
                .filter(MarketIndex.code == cfg["code"], MarketIndex.trade_date == today)
                .first()
            )
            if existing:
                existing.open = open_p; existing.high = high; existing.low = low
                existing.close = current; existing.change = round(change, 2)
                existing.change_pct = round(change_pct, 2)
            else:
                db.add(MarketIndex(
                    code=cfg["code"], name=cfg["name"], trade_date=today,
                    open=open_p, high=high, low=low, close=current,
                    change=round(change, 2), change_pct=round(change_pct, 2),
                ))
                inserted += 1
        db.commit()
        logger.info(f"Market indices: {inserted} new")
        return {"indices": len(INDEX_CONFIG), "inserted": inserted}
    except Exception as e:
        logger.error(f"Index crawl failed: {e}")
        raise
    finally:
        if close_db and db:
            db.close()


def crawl_market_breadth(db: Session | None = None) -> dict:
    """Calculate up/down/flat counts from latest K-line data."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        from sqlalchemy import func as sqla_func

        latest_date = db.query(sqla_func.max(DailyKline.trade_date)).scalar()
        if not latest_date:
            return {"breadth": 0}

        boards = {"SH": "沪市", "SZ": "深市", "BJ": "北交所"}
        inserted = 0
        for board_code in boards:
            stocks = db.query(Stock).filter(Stock.exchange == board_code, Stock.is_active == 1).all()
            up = down = flat = 0
            for s in stocks:
                k = (
                    db.query(DailyKline)
                    .filter(DailyKline.stock_id == s.id, DailyKline.trade_date == latest_date)
                    .first()
                )
                if k:
                    chg = k.close - k.open
                    if chg > 0: up += 1
                    elif chg < 0: down += 1
                    else: flat += 1
            total = up + down + flat
            if total == 0:
                continue

            existing = (
                db.query(MarketBreadth)
                .filter(MarketBreadth.board == board_code, MarketBreadth.trade_date == latest_date)
                .first()
            )
            if existing:
                existing.total = total; existing.up_count = up
                existing.down_count = down; existing.flat_count = flat
            else:
                db.add(MarketBreadth(
                    board=board_code, trade_date=latest_date,
                    total=total, up_count=up, down_count=down, flat_count=flat,
                ))
                inserted += 1
        db.commit()
        logger.info(f"Market breadth: {inserted} new boards")
        return {"boards": len(boards), "inserted": inserted}
    except Exception as e:
        logger.error(f"Breadth crawl failed: {e}")
        raise
    finally:
        if close_db and db:
            db.close()


def crawl_sectors(db: Session | None = None) -> dict:
    """Crawl sector/板块 rankings from East Money."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        today = date.today()
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "30", "po": "1", "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f12,f14,f100,f102",
        }
        hdrs = {**HEADERS, "Referer": "http://quote.eastmoney.com/"}
        resp = requests.get(url, params=params, headers=hdrs, timeout=15)
        data = resp.json()
        items = data.get("data", {}).get("diff", [])
        inserted = 0

        for rank, item in enumerate(items, 1):
            code = item.get("f12", ""); name = item.get("f14", "")
            change_pct = float(item.get("f3", 0) or 0)
            if not code or not name:
                continue
            existing = (
                db.query(SectorData)
                .filter(SectorData.code == code, SectorData.trade_date == today)
                .first()
            )
            if existing:
                existing.change_pct = round(change_pct, 2)
                existing.rank = rank
                existing.leading_stock = item.get("f100") or None
                existing.leading_stock_change = round(float(item.get("f102", 0) or 0), 2) if item.get("f102") else None
            else:
                db.add(SectorData(
                    code=code, name=name, trade_date=today,
                    change_pct=round(change_pct, 2), rank=rank,
                    leading_stock=item.get("f100") or None,
                    leading_stock_change=round(float(item.get("f102", 0) or 0), 2) if item.get("f102") else None,
                ))
                inserted += 1
        db.commit()
        logger.info(f"Sectors: {inserted} new")
        return {"sectors": len(items), "inserted": inserted}
    except Exception as e:
        logger.error(f"Sector crawl failed: {e}")
        raise
    finally:
        if close_db and db:
            db.close()


def crawl_all_market_data() -> dict:
    """Run all market crawls, return summary."""
    db = SessionLocal()
    try:
        r = {}
        try: r["indices"] = crawl_market_indices(db)
        except Exception as e: r["indices"] = {"error": str(e)}
        try: r["breadth"] = crawl_market_breadth(db)
        except Exception as e: r["breadth"] = {"error": str(e)}
        try: r["sectors"] = crawl_sectors(db)
        except Exception as e: r["sectors"] = {"error": str(e)}
        try: r["index_kline"] = crawl_index_kline_all(db)
        except Exception as e: r["index_kline"] = {"error": str(e)}
        try: r["turnover"] = crawl_market_turnover(db)
        except Exception as e: r["turnover"] = {"error": str(e)}
        return r
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════
# Index K-line
# ═══════════════════════════════════════════════════════════

def crawl_index_kline(code: str, name: str, db: Session, datalen: int = 400) -> int:
    """Crawl daily K-line for a market index. Returns inserted count."""
    symbol = code  # Already in Sina format: sh000001, sz399001

    params = {
        "symbol": symbol,
        "scale": "240",
        "ma": "no",
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
                td = date(int(trade_date_str[:4]), int(trade_date_str[4:6]), int(trade_date_str[6:8]))
            elif "-" in trade_date_str:
                td = date.fromisoformat(trade_date_str)
            else:
                continue

            existing = (
                db.query(IndexKline)
                .filter(IndexKline.code == code, IndexKline.trade_date == td)
                .first()
            )
            if existing:
                continue

            db.add(IndexKline(
                code=code, name=name, trade_date=td,
                open=float(item["open"]), high=float(item["high"]),
                low=float(item["low"]), close=float(item["close"]),
                volume=int(float(item["volume"])),
                amount=float(item.get("amount", 0) or 0),
            ))
            inserted += 1

        db.commit()
        return inserted
    except Exception as e:
        logger.warning(f"Failed to crawl index K-line for {code}: {e}")
        return 0


def crawl_index_kline_all(db: Session | None = None) -> dict:
    """Crawl K-line for all tracked indices."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        total = 0
        for cfg in INDEX_CONFIG:
            n = crawl_index_kline(cfg["code"], cfg["name"], db)
            total += n
            time.sleep(0.3)
        return {"indices": len(INDEX_CONFIG), "records": total}
    finally:
        if close_db and db:
            db.close()


# ═══════════════════════════════════════════════════════════
# Market Turnover
# ═══════════════════════════════════════════════════════════

def crawl_market_turnover(db: Session | None = None) -> dict:
    """Calculate total market turnover from daily K-line data."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        from sqlalchemy import func as sqla_func

        # Get latest date with K-line data
        latest_date = db.query(sqla_func.max(DailyKline.trade_date)).scalar()
        if not latest_date:
            return {"error": "No K-line data available"}

        # Sum amount and volume for the latest date
        row = (
            db.query(
                sqla_func.sum(DailyKline.amount).label("total_amount"),
                sqla_func.sum(DailyKline.volume).label("total_volume"),
                sqla_func.count(DailyKline.id).label("stock_count"),
            )
            .filter(DailyKline.trade_date == latest_date)
            .first()
        )

        total_amount = float(row.total_amount or 0)
        total_volume = int(row.total_volume or 0)
        stock_count = int(row.stock_count or 0)

        existing = (
            db.query(MarketTurnover)
            .filter(MarketTurnover.trade_date == latest_date)
            .first()
        )
        if existing:
            existing.total_amount = total_amount
            existing.total_volume = total_volume
            existing.stock_count = stock_count
        else:
            db.add(MarketTurnover(
                trade_date=latest_date,
                total_amount=total_amount,
                total_volume=total_volume,
                stock_count=stock_count,
            ))

        db.commit()
        logger.info(f"Market turnover: date={latest_date}, amount={total_amount:.0f}")
        return {"date": str(latest_date), "amount": total_amount, "volume": total_volume, "stocks": stock_count}
    finally:
        if close_db and db:
            db.close()
