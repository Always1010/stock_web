#!/usr/bin/env python3
"""CLI tools for manual stock data crawling and NAV updates."""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("cli")


def main():
    parser = argparse.ArgumentParser(description="Stock Web CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # crawl-stock-list
    subparsers.add_parser("crawl-stock-list", help="Crawl A-share stock list")

    # crawl-kline
    kline_parser = subparsers.add_parser("crawl-kline", help="Crawl K-line data")
    kline_parser.add_argument("--code", type=str, help="Specific stock code to crawl")
    kline_parser.add_argument("--all", action="store_true", help="Crawl all active stocks")

    # update-nav
    subparsers.add_parser("update-nav", help="Update NAV for all portfolios")

    args = parser.parse_args()

    if args.command == "crawl-stock-list":
        from app.services.crawler import crawl_stock_list
        logger.info("Starting stock list crawl...")
        result = crawl_stock_list()
        print(f"Done: {result}")

    elif args.command == "crawl-kline":
        from app.database import SessionLocal
        from app.models.stock import Stock
        from app.services.crawler import crawl_all_kline, crawl_kline_for_stock

        db = SessionLocal()
        try:
            if args.code:
                stock = db.query(Stock).filter(Stock.code == args.code).first()
                if not stock:
                    print(f"Stock {args.code} not found. Run crawl-stock-list first.")
                    sys.exit(1)
                logger.info(f"Crawling K-line for {stock.code} {stock.name}...")
                inserted = crawl_kline_for_stock(stock, db)
                print(f"Inserted {inserted} records for {stock.code}")
            elif args.all:
                logger.info("Crawling K-line for all active stocks...")
                result = crawl_all_kline(db)
                print(f"Done: {result}")
            else:
                print("Specify --code <CODE> or --all")
        finally:
            db.close()

    elif args.command == "update-nav":
        from app.services.portfolio_service import update_all_portfolios_nav
        logger.info("Updating portfolio NAVs...")
        result = update_all_portfolios_nav()
        print(f"Done: {result}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
