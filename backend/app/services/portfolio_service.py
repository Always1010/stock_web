"""
组合业务逻辑层 — 净值计算、成本价策略、收益贡献分析、数据刷新。

本模块是组合管理的核心业务层，负责：
  1. 组合代码生成    — 按日期 + 序号生成唯一 6 位组合代码
  2. 成本价策略      — 根据用户输入 / 当前时间 / 最新收盘价自动确定持仓成本
  3. 净值计算        — 逐日计算组合总市值与总成本，写入 NAV 历史表
  4. 收益贡献分析    — 计算每只持仓对组合整体收益的贡献度
  5. K 线数据刷新    — 为组合内所有持仓股票爬取日 K 线数据
  6. NAV 重算        — 全量/增量重建组合净值历史

与 routers/portfolio.py（API 层）的关系：
  - router 层负责 HTTP 请求处理、参数校验、权限检查、响应组装
  - service 层负责纯业务逻辑，不感知 HTTP 协议细节
  - router 调用 service，service 不依赖 router
"""
import logging
import time
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioNavHistory
from app.models.stock import DailyKline
from app.schemas.portfolio import ContributionItem
from app.utils.date_utils import is_after_3pm, now_cst, today_cst

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# 一、组合代码生成
# ══════════════════════════════════════════════════════════════════════

def generate_portfolio_code(db: Session) -> str:
    """
    生成唯一的组合代码。

    格式: PF{YYYYMMDD}{NNN}
      - PF          固定前缀，表示 Portfolio
      - YYYYMMDD    创建日期（北京时间）
      - NNN         当日序号，从 001 开始递增

    例如: PF20250625001 表示 2025-06-25 创建的第 1 个组合。

    实现:
      查询当天已有的最大序号，在其基础上 +1。
      若当天尚无组合，则从 001 开始。
      序号上限 999（同一天创建超过 999 个组合时溢出，实际场景不会发生）。
    """
    today_str = today_cst().strftime("%Y%m%d")
    prefix = f"PF{today_str}"

    # 查询当天已创建的最大序号（按 code 降序取第一条）
    last = (
        db.query(Portfolio)
        .filter(Portfolio.code.like(f"{prefix}%"))
        .order_by(Portfolio.code.desc())
        .first()
    )

    if last:
        # 取后三位序号 +1
        last_seq = int(last.code[-3:])
        new_seq = last_seq + 1
    else:
        new_seq = 1

    return f"{prefix}{new_seq:03d}"


# ══════════════════════════════════════════════════════════════════════
# 二、成本价策略
# ══════════════════════════════════════════════════════════════════════

def get_latest_close(
    stock_id: int, db: Session, before_date: date | None = None
) -> float | None:
    """
    获取某只股票的最新收盘价。

    参数:
      stock_id    — 股票 ID
      db          — 数据库会话
      before_date — 可选，只查询此日期之前的 K 线（用于"取昨日收盘"场景）

    返回:
      最新收盘价（float），若无 K 线数据则返回 None

    查询逻辑:
      从 DailyKline 表按 trade_date 降序取第一条记录的 close 字段。
      如果指定了 before_date，则只查该日期之前的 K 线（不包含当日）。
    """
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
    为持仓设定成本价，实现智能成本价策略。

    策略规则（按优先级）:

      规则 1 — 用户手动指定
        如果用户在添加持仓时传入了 cost_price，直接使用该价格。
        设置后成本价即锁定（is_cost_locked = True），后续不可自动覆盖。

      规则 2 — 下午 3 点后添加（收盘后）
        尝试取当日收盘价作为成本价。
        如果当天不是交易日（无当日 K 线），则回退到最近一个交易日的收盘价。
        这模拟了"以今日收盘价买入"的真实场景。

      规则 3 — 下午 3 点前添加（盘中）
        取前一个交易日的收盘价作为成本价。
        因为当日收盘价尚未确定，无法作为成本基准。

    边界情况:
      - 若成本价已锁定（is_cost_locked），直接返回不修改
      - 若数据库中无任何 K 线数据，cost_price 保持 None（需后续手动设定）

    返回:
      更新后的 holding 对象（cost_price 可能仍为 None）
    """
    # 已锁定的成本价不可修改
    if holding.is_cost_locked:
        return holding

    # 规则 1: 用户手动传入了成本价，直接使用
    if user_provided_cost is not None:
        holding.cost_price = user_provided_cost
        holding.cost_price_set_at = datetime.utcnow()
        return holding

    # 规则 2 & 3: 根据当前时间自动判断
    today = today_cst()

    if is_after_3pm():
        # ── 下午 3 点后：优先取当日收盘价 ──
        today_close = get_latest_close(holding.stock_id, db, before_date=None)
        # 确认该收盘价确实来自今天（而非更早日期）
        today_kline = (
            db.query(DailyKline)
            .filter(
                DailyKline.stock_id == holding.stock_id,
                DailyKline.trade_date == today,
            )
            .first()
        )
        if today_kline:
            # 今天是交易日，使用当日收盘价
            holding.cost_price = today_kline.close
        elif today_close is not None:
            # 周末/节假日：回退到最近一个交易日的收盘价
            holding.cost_price = today_close
    else:
        # ── 下午 3 点前：取前一交易日收盘价 ──
        prev_close = get_latest_close(holding.stock_id, db, before_date=today)
        if prev_close is not None:
            holding.cost_price = prev_close

    # 记录成本价设定时间
    if holding.cost_price is not None:
        holding.cost_price_set_at = datetime.utcnow()

    return holding


# ══════════════════════════════════════════════════════════════════════
# 三、净值（NAV）计算
# ══════════════════════════════════════════════════════════════════════

def update_portfolio_nav(portfolio: Portfolio, db: Session) -> PortfolioNavHistory | None:
    """
    计算并记录单个组合的当日净值（NAV）。

    计算公式:
      总市值   = Σ(每只持仓股数 × 该股最新收盘价)
      总成本   = Σ(每只持仓股数 × 该股成本价)  [成本价未设定则不计入]

    派生字段（日收益、累计收益率）在 API 端点中实时计算，
    此处仅存储原始净值数据 nav / total_cost / total_market_value。

    支持幂等写入:
      如果当日 NAV 记录已存在（如重复触发），执行 UPDATE 而非 INSERT。

    返回:
      新建或更新后的 PortfolioNavHistory 记录；若无价格数据则返回 None。

    调用方:
      - 定时调度器（每个交易日 15:05 触发 update_all_portfolios_nav）
      - 手动触发 NAV 重算
    """
    today = today_cst()

    total_market_value = 0.0
    total_cost = 0.0

    # 遍历组合内所有持仓，累加市值和成本
    for holding in portfolio.holdings:
        close = get_latest_close(holding.stock_id, db)
        if close is None:
            logger.warning(
                f"No price data for stock {holding.stock.code} in portfolio {portfolio.code}"
            )
            continue  # 跳过无价格数据的股票

        market_value = holding.shares * close
        total_market_value += market_value

        # 成本价未设定则不参与成本累计
        if holding.cost_price is not None:
            total_cost += holding.shares * holding.cost_price

    # 查询昨日 NAV（预留用于后续派生计算，当前派生字段在 API 层实时计算）
    yesterday_nav = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date < today,
        )
        .order_by(PortfolioNavHistory.nav_date.desc())
        .first()
    )

    # 派生字段统一设为 None，由 API 端点实时计算
    # （daily-returns / monthly-returns / nav 端点均有独立的派生计算逻辑）
    daily_return = None
    daily_return_rate = None
    cum_return_rate = None

    # 幂等处理：检查当日是否已有 NAV 记录
    existing = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date == today,
        )
        .first()
    )

    if existing:
        # 已有记录 → 更新（例如收盘价变化后重新计算）
        existing.nav = total_market_value
        existing.daily_return = daily_return
        existing.daily_return_rate = daily_return_rate
        existing.cum_return_rate = cum_return_rate
        existing.total_cost = total_cost
        existing.total_market_value = total_market_value
        db.commit()
        return existing

    # 新建记录
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
    """
    批量更新所有组合的当日净值。

    由定时调度器在每个交易日 15:05 自动调用（收盘后 5 分钟）。
    遍历全部组合，依次调用 update_portfolio_nav。

    参数:
      db — 可选的数据库会话。若不传则在此函数内自行创建和关闭。

    返回:
      {"updated": N, "errors": N} — 成功更新的组合数和失败数

    容错:
      单个组合更新失败不影响其他组合，错误仅记录日志并计入 errors 计数。
    """
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
        # 函数内部创建的会话由函数负责关闭
        if close_db and db:
            db.close()


# ══════════════════════════════════════════════════════════════════════
# 四、收益贡献分析
# ══════════════════════════════════════════════════════════════════════

def calculate_contributions(
    portfolio: Portfolio,
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ContributionItem]:
    """
    计算组合中每只持仓股票对整体收益的贡献度。

    计算逻辑:
      对每只持仓股票:
        1. 获取区间起始日的收盘价（start_price）和截止日的收盘价（end_price）
        2. 区间收益金额 = (end_price - base_price) × 持股数
        3. 区间收益率   = (end_price / base_price) - 1
        4. 贡献占比     = 该股票收益金额 / 组合总成本

    基准价（base_price）确定规则:
      - 单日查询（start == end）: 用前一交易日收盘价作为基准，
        若前一交易日无数据则回退到 start_price
      - 多日查询: 用期间起始价（start_price），若无则回退到持仓成本价

    参数:
      portfolio  — 组合对象
      db         — 数据库会话
      start_date — 分析起始日期，None 表示从最早可用数据开始
      end_date   — 分析截止日期，None 表示到最新可用数据为止

    返回:
      ContributionItem 列表，每只持仓一条（包含收益金额、收益率、贡献占比）
    """
    items = []

    for holding in portfolio.holdings:
        stock = holding.stock

        # ── 查询起始日和截止日的收盘价 ──
        start_kline = None
        end_kline = None

        kline_query = db.query(DailyKline).filter(DailyKline.stock_id == stock.id)

        if start_date:
            # 指定了起始日：取 >= start_date 的第一条 K 线
            start_kline = (
                kline_query.filter(DailyKline.trade_date >= start_date)
                .order_by(DailyKline.trade_date.asc())
                .first()
            )
        else:
            # 未指定：取历史第一条 K 线
            start_kline = kline_query.order_by(DailyKline.trade_date.asc()).first()

        if end_date:
            # 指定了截止日：取 <= end_date 的最后一条 K 线
            end_kline = (
                kline_query.filter(DailyKline.trade_date <= end_date)
                .order_by(DailyKline.trade_date.desc())
                .first()
            )
        else:
            # 未指定：取最新一条 K 线
            end_kline = kline_query.order_by(DailyKline.trade_date.desc()).first()

        start_price = start_kline.close if start_kline else None
        end_price = end_kline.close if end_kline else None

        # 当前市值 = 持股数 × 最新价
        market_value = holding.shares * end_price if end_price else 0.0

        return_amount = None
        return_rate = None
        contribution_pct = None

        # ── 确定收益计算基准价 ──
        if start_date and end_date and start_date == end_date and end_price is not None:
            # 单日查询：用前一交易日收盘价作为基准（反映当日变化）
            prev_kline = (
                db.query(DailyKline)
                .filter(
                    DailyKline.stock_id == stock.id,
                    DailyKline.trade_date < start_date,
                )
                .order_by(DailyKline.trade_date.desc())
                .first()
            )
            if prev_kline and prev_kline.close > 0:
                base_price = prev_kline.close
            else:
                base_price = start_price
        else:
            # 多日查询：用期间起始价作为基准
            base_price = start_price if start_price is not None else holding.cost_price

        # ── 计算收益 ──
        if base_price is not None and end_price is not None and base_price > 0:
            return_amount = (end_price - base_price) * holding.shares
            return_rate = (end_price / base_price) - 1

            # 贡献占比 = 该股收益 / 组合总成本
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


# ══════════════════════════════════════════════════════════════════════
# 五、组合级 K 线数据刷新
# ══════════════════════════════════════════════════════════════════════

def refresh_portfolio_kline(
    portfolio: Portfolio,
    db: Session,
    overwrite: bool = False,
) -> dict:
    """
    为组合内所有持仓股票爬取日 K 线数据。

    遍历组合的每只持仓，调用爬虫服务拉取该股票的 K 线数据。

    参数:
      portfolio — 目标组合
      db        — 数据库会话
      overwrite — True = 全量刷新（删除旧数据后重新插入）
                  False = 增量刷新（只插入缺失的日期）

    限速:
      每只股票之间 sleep 0.5 秒，避免对数据源造成过大压力。

    返回:
      {
        "portfolio_code":  组合代码,
        "total_stocks":    持仓股票总数,
        "processed":       成功处理的股票数,
        "total_affected":  新增/更新的 K 线条数,
        "errors":          失败的股票数
      }
    """
    from app.services.crawler import crawl_kline_for_stock

    holdings = list(portfolio.holdings)
    if not holdings:
        return {
            "portfolio_code": portfolio.code,
            "total_stocks": 0,
            "processed": 0,
            "total_affected": 0,
            "errors": 0,
        }

    total_affected = 0
    processed = 0
    errors = 0

    for holding in holdings:
        stock = holding.stock
        if not stock:
            continue
        try:
            # 调用爬虫服务抓取该股票的 K 线数据
            affected = crawl_kline_for_stock(stock, db, overwrite=overwrite)
            total_affected += affected
            processed += 1
            time.sleep(0.5)  # 请求间隔，防止被数据源限流
        except Exception as e:
            errors += 1
            logger.error(f"Failed to refresh {stock.code}: {e}")

    # 有数据变更时统一提交
    if total_affected > 0:
        db.commit()

    return {
        "portfolio_code": portfolio.code,
        "total_stocks": len(holdings),
        "processed": processed,
        "total_affected": total_affected,
        "errors": errors,
    }


# ══════════════════════════════════════════════════════════════════════
# 六、NAV 重算辅助函数
# ══════════════════════════════════════════════════════════════════════

def _get_holdings_trading_dates(
    portfolio: Portfolio,
    db: Session,
    start_date: date,
    end_date: date,
) -> list[date]:
    """
    获取组合所有持仓股票在指定日期范围内的交易日合集。

    实现:
      收集所有持仓的 stock_id，查询 DailyKline 表中这些股票在范围内
      出现过的所有不重复交易日期，按日期升序返回。

    用途:
      作为 NAV 重算的"日历"——只在有交易数据的日期生成 NAV 记录，
      避免在周末/节假日产生空记录。

    返回:
      日期列表，如 [date(2025,6,23), date(2025,6,24), date(2025,6,25)]
    """
    stock_ids = [h.stock_id for h in portfolio.holdings]
    if not stock_ids:
        return []

    rows = (
        db.query(DailyKline.trade_date)
        .filter(
            DailyKline.stock_id.in_(stock_ids),
            DailyKline.trade_date >= start_date,
            DailyKline.trade_date <= end_date,
        )
        .distinct()
        .order_by(DailyKline.trade_date.asc())
        .all()
    )
    # rows 是单元素元组列表 [(date1,), (date2,), ...]，解包为纯日期列表
    return [r[0] for r in rows]


def _compute_nav_for_date(
    portfolio: Portfolio,
    db: Session,
    target_date: date,
) -> tuple[float, float, float | None, float | None, float | None]:
    """
    计算组合在指定日期的净值指标。

    计算逻辑与 update_portfolio_nav 一致:
      - 总市值 = Σ(股数 × 该日收盘价)
      - 总成本 = Σ(股数 × 成本价)

    关键差异:
      查询收盘价时使用 before_date = target_date + 1天，
      这样可以取到 target_date 当天及之前的最新收盘价。
      （get_latest_close 使用 < before_date 过滤，+1 天后等价于 <= target_date）

    派生字段（daily_return / daily_return_rate / cum_return_rate）
    统一返回 None，由 API 层实时计算。

    返回:
      (total_market_value, total_cost, daily_return, daily_return_rate, cum_return_rate)
    """
    total_market_value = 0.0
    total_cost = 0.0

    for holding in portfolio.holdings:
        # 取 target_date 当天及之前的最新收盘价
        close = get_latest_close(
            holding.stock_id, db, before_date=target_date + timedelta(days=1)
        )
        if close is None:
            continue
        total_market_value += holding.shares * close
        if holding.cost_price is not None:
            total_cost += holding.shares * holding.cost_price

    # 派生字段在 API 层实时计算，此处不重复计算
    daily_return = None
    daily_return_rate = None
    cum_return_rate = None

    return total_market_value, total_cost, daily_return, daily_return_rate, cum_return_rate


# ══════════════════════════════════════════════════════════════════════
# 七、全量与增量 NAV 重算
# ══════════════════════════════════════════════════════════════════════

def recalculate_portfolio_nav(
    portfolio: Portfolio,
    db: Session,
    start_date: date | None = None,
) -> dict:
    """
    全量 NAV 重算：删除指定起始日之后的 NAV 记录，逐日重新计算。

    适用场景:
      - 修改了持仓成本价后，需要让历史收益反映新成本
      - 修改了收益起始日
      - 添加或删除了持仓，需要重建净值曲线
      - 怀疑 NAV 数据不一致

    流程:
      1. 确定起始日: 优先用传入的 start_date，否则用 portfolio.return_start_date，都无则用今天
      2. 删除从起始日起的所有 NAV 历史记录
      3. 获取起始日到今天的全部交易日列表
      4. 逐日计算净值并写入（每 50 条提交一次，兼顾性能与事务大小）

    边界处理:
      - 起始日在未来 → 直接返回，不计算
      - 无可用交易数据 → 返回提示信息
      - 某日总市值和总成本均为 0 → 跳过该日（不生成空记录）

    返回:
      {
        "portfolio_code":  组合代码,
        "start_date":      重算起始日,
        "end_date":        重算截止日,
        "records_created": 生成的 NAV 记录数
      }
    """
    today = today_cst()
    if start_date is None:
        start_date = portfolio.return_start_date or today

    # 起始日在未来，无需计算
    if start_date > today:
        return {
            "portfolio_code": portfolio.code,
            "start_date": str(start_date),
            "end_date": str(today),
            "records_created": 0,
            "message": "起始日期在未来，无需计算",
        }

    # 第一步：删除起始日之后的旧 NAV 记录
    deleted = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date >= start_date,
        )
        .delete()
    )

    # 第二步：获取交易日列表（去重 + 排序）
    trading_dates = _get_holdings_trading_dates(portfolio, db, start_date, today)
    if not trading_dates:
        db.commit()
        return {
            "portfolio_code": portfolio.code,
            "start_date": str(start_date),
            "end_date": str(today),
            "records_created": 0,
            "message": "无可用交易数据",
        }

    # 第三步：逐日计算并写入 NAV
    created = 0
    for trade_date in trading_dates:
        mv, cost, dr, drr, crr = _compute_nav_for_date(portfolio, db, trade_date)

        # 无有效数据（市值和成本均为 0），跳过
        if mv == 0 and cost == 0:
            continue

        nav_record = PortfolioNavHistory(
            portfolio_id=portfolio.id,
            nav_date=trade_date,
            nav=mv,
            daily_return=dr,
            daily_return_rate=drr,
            cum_return_rate=crr,
            total_cost=cost,
            total_market_value=mv,
        )
        db.add(nav_record)
        created += 1

        # 每 50 条提交一次，避免单次事务过大
        if created % 50 == 0:
            db.commit()

    # 提交剩余记录
    if created > 0:
        db.commit()

    logger.info(
        f"NAV recalc for {portfolio.code}: deleted {deleted}, created {created}"
    )
    return {
        "portfolio_code": portfolio.code,
        "start_date": str(start_date),
        "end_date": str(today),
        "records_created": created,
    }


def fill_missing_nav(portfolio: Portfolio, db: Session) -> dict:
    """
    增量 NAV 填充：找到最新 NAV 日期，补充缺失日期到今日。

    与全量重算的区别:
      - 全量: 删除旧数据 → 从头重建（适用场景：成本价变更、持仓变化）
      - 增量: 保留旧数据 → 只补最新日期（适用场景：每日自动更新、快速补数据）

    起始日确定逻辑（优先级从高到低）:
      1. 最新 NAV 日期的下一天（已有数据，续补）
      2. portfolio.return_start_date（无 NAV 但有收益起始日）
      3. 持仓最早交易日期（全新组合，自动探测）

    流程:
      1. 查最新 NAV 日期 → 若已覆盖到今天，直接返回"已是最新"
      2. 确定起始日
      3. 获取起始日到今天的交易日列表
      4. 逐日计算并写入（已存在的日期会跳过，因为 _get_holdings_trading_dates
         返回的是所有交易日，但写入前不做唯一性检查 —— 调用方需确保不重复）

    返回:
      {
        "portfolio_code":  组合代码,
        "start_date":      填充起始日,
        "end_date":        填充截止日（今天）,
        "records_created": 新生成的 NAV 记录数
      }
    """
    today = today_cst()

    # 第一步：查最新 NAV 日期
    latest_nav = (
        db.query(PortfolioNavHistory)
        .filter(PortfolioNavHistory.portfolio_id == portfolio.id)
        .order_by(PortfolioNavHistory.nav_date.desc())
        .first()
    )

    # 已是最新，无需填充
    if latest_nav and latest_nav.nav_date >= today:
        return {
            "portfolio_code": portfolio.code,
            "start_date": str(latest_nav.nav_date),
            "end_date": str(today),
            "records_created": 0,
            "message": "收益数据已是最新",
        }

    # 第二步：确定起始日
    if latest_nav:
        # 有历史 NAV：从最后一条的下一天开始
        start_from = latest_nav.nav_date + timedelta(days=1)
    elif portfolio.return_start_date:
        # 无历史 NAV 但有收益起始日
        start_from = portfolio.return_start_date
    else:
        # 全新组合：探测最早交易日
        earliest = _get_holdings_trading_dates(
            portfolio, db, date(2000, 1, 1), today
        )
        if not earliest:
            return {
                "portfolio_code": portfolio.code,
                "start_date": str(today),
                "end_date": str(today),
                "records_created": 0,
                "message": "无可用交易数据",
            }
        start_from = earliest[0]

    # 第三步：获取交易日列表
    trading_dates = _get_holdings_trading_dates(portfolio, db, start_from, today)
    if not trading_dates:
        return {
            "portfolio_code": portfolio.code,
            "start_date": str(start_from),
            "end_date": str(today),
            "records_created": 0,
            "message": "无新的交易日需要填补",
        }

    # 第四步：逐日计算并写入
    created = 0
    for trade_date in trading_dates:
        mv, cost, dr, drr, crr = _compute_nav_for_date(portfolio, db, trade_date)

        if mv == 0 and cost == 0:
            continue

        nav_record = PortfolioNavHistory(
            portfolio_id=portfolio.id,
            nav_date=trade_date,
            nav=mv,
            daily_return=dr,
            daily_return_rate=drr,
            cum_return_rate=crr,
            total_cost=cost,
            total_market_value=mv,
        )
        db.add(nav_record)
        created += 1

        if created % 50 == 0:
            db.commit()

    if created > 0:
        db.commit()

    return {
        "portfolio_code": portfolio.code,
        "start_date": str(start_from),
        "end_date": str(today),
        "records_created": created,
    }
