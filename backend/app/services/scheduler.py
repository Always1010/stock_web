"""APScheduler configuration for scheduled crawling and NAV updates."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=settings.TIMEZONE)


def _crawl_job():
    """Daily crawl job: update stock list and K-line data, then refresh market stats."""
    from app.database import SessionLocal
    from app.services.crawler import crawl_all_kline, crawl_all_market_data, crawl_stock_list

    logger.info("Scheduled crawl job starting...")
    db = SessionLocal()
    try:
        result_list = crawl_stock_list(db)
        result_kline = crawl_all_kline(db)
        result_market = crawl_all_market_data()
        logger.info(
            f"Crawl job done: list={result_list}, kline={result_kline}, market={result_market}"
        )
    except Exception as e:
        logger.error(f"Crawl job failed: {e}")
    finally:
        db.close()


def _nav_update_job():
    """Daily NAV update job: calculate NAV, crawl market data."""
    from app.services.crawler import crawl_all_market_data
    from app.services.portfolio_service import update_all_portfolios_nav

    logger.info("Scheduled NAV update job starting...")
    try:
        result = update_all_portfolios_nav()
        logger.info(f"NAV update job done: {result}")
    except Exception as e:
        logger.error(f"NAV update job failed: {e}")

    logger.info("Scheduled market data crawl starting...")
    try:
        result = crawl_all_market_data()
        logger.info(f"Market data crawl done: {result}")
    except Exception as e:
        logger.error(f"Market data crawl failed: {e}")


def start_scheduler():
    """Start the APScheduler with crawl and NAV update jobs."""
    scheduler.add_job(
        _crawl_job,
        trigger="cron",
        hour=settings.CRAWL_HOUR,
        minute=settings.CRAWL_MINUTE,
        id="daily_crawl",
        replace_existing=True,
    )

    scheduler.add_job(
        _nav_update_job,
        trigger="cron",
        hour=settings.NAV_UPDATE_HOUR,
        minute=settings.NAV_UPDATE_MINUTE,
        id="daily_nav_update",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started: crawl at {settings.CRAWL_HOUR:02d}:{settings.CRAWL_MINUTE:02d}, "
        f"NAV at {settings.NAV_UPDATE_HOUR:02d}:{settings.NAV_UPDATE_MINUTE:02d}"
    )


def shutdown_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
