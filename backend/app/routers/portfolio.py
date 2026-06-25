"""
组合路由模块 — 投资组合的 CRUD、持仓管理、成本价设定、NAV 净值曲线与分析。

本模块是组合管理功能的核心 API 层，提供以下功能组：
  1. 组合 CRUD      — 创建/查看/修改/删除投资组合
  2. 持仓管理        — 添加/修改/删除持仓股票，设定成本价
  3. 图表与分析      — NAV 历史曲线、日收益日历、月收益汇总、单股贡献分析
  4. 收益起始日      — 设定收益计算的起始日期
  5. 数据刷新        — 全量/增量爬取持仓股票的 K 线数据
  6. NAV 重算       — 全量/增量重新计算组合净值历史

所有接口均要求用户认证（JWT），且只能操作当前登录用户自己的组合。

计算职责说明：
  本模块中的日收益、月收益、累计收益率等派生计算属于「便捷计算」——
  后端提供加工好的数据方便前端直接使用，但这些计算理论上都可以在前端完成。
  前端拿到原始 NAV 序列（nav + total_cost + date）后即可自行算出所有衍生指标，
  计算压力可以从后端转移到客户端。各端点中标注「前端也可完成」的计算均属此类。
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.portfolio import Portfolio, PortfolioHolding, PortfolioNavHistory
from app.models.stock import DailyKline, Stock
from app.models.user import User
from app.schemas.portfolio import (
    AddHoldingRequest,
    ContributionItem,
    ContributionResponse,
    DailyReturnItem,
    DailyReturnsResponse,
    HoldingKlineItem,
    HoldingsKlineResponse,
    HoldingResponse,
    KlinePoint,
    MonthlyReturnItem,
    MonthlyReturnsResponse,
    NavHistoryItem,
    NavHistoryResponse,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioNavRecalcResponse,
    PortfolioRefreshResponse,
    PortfolioSummary,
    PortfolioUpdate,
    SetCostPriceRequest,
    SetReturnStartDateRequest,
    UpdateHoldingRequest,
)
from app.services.portfolio_service import (
    calculate_contributions,
    fill_missing_nav,
    generate_portfolio_code,
    get_latest_close,
    recalculate_portfolio_nav,
    refresh_portfolio_kline,
    set_holding_cost_price,
)
from app.utils.security import get_current_user

# ── 路由实例 ────────────────────────────────────────────────────────
# 所有路由均以 /portfolios 为前缀，在 OpenAPI 文档中归入 "Portfolios" 分组
router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


# ══════════════════════════════════════════════════════════════════════
# 内部辅助函数
# ══════════════════════════════════════════════════════════════════════

def _get_user_portfolio(
    code: str, db: Session, current_user: User
) -> Portfolio:
    """
    根据组合代码查找组合，同时校验归属权。

    这是一个内部 helper，所有需要按 code 查找组合的路由都会调用它，
    避免了重复的查询 + 404 判断逻辑。

    参数:
        code:          组合的 6 位唯一代码（如 "A3F8K2"）
        db:            数据库会话
        current_user:  当前登录用户（由 JWT 中间件注入）

    返回:
        匹配的 Portfolio ORM 对象

    异常:
        HTTPException 404 — 组合不存在或不属于当前用户
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found"
        )
    return portfolio


# ══════════════════════════════════════════════════════════════════════
# 一、组合 CRUD（创建 / 列表 / 详情 / 更新 / 删除）
# ══════════════════════════════════════════════════════════════════════

@router.get("", response_model=list[PortfolioSummary])
def list_portfolios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的所有组合列表（概要信息）。

    返回每个组合的：
      - 基本信息（代码、名称、创建时间、收益起始日）
      - 最新 NAV（净值）
      - 最新累计收益金额  = 总市值 - 总成本
      - 最新累计收益率    = (总市值 / 总成本) - 1

    按创建时间倒序排列，最新创建的在前。
    """
    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == current_user.id)
        .order_by(Portfolio.created_at.desc())
        .all()
    )

    result = []
    for p in portfolios:
        # 查询该组合最新的 NAV 记录（按日期降序取第一条）
        latest_nav = (
            db.query(PortfolioNavHistory)
            .filter(PortfolioNavHistory.portfolio_id == p.id)
            .order_by(PortfolioNavHistory.nav_date.desc())
            .first()
        )
        # 便捷计算（前端也可完成）：累计收益 = 总市值 - 总成本，仅当成本 > 0 时有效
        cum_return = None
        if latest_nav and latest_nav.total_cost and latest_nav.total_cost > 0:
            cum_return = latest_nav.total_market_value - latest_nav.total_cost
        result.append(
            PortfolioSummary(
                code=p.code,
                name=p.name,
                created_at=p.created_at,
                return_start_date=p.return_start_date,
                latest_nav=latest_nav.nav if latest_nav else None,
                latest_total_cost=latest_nav.total_cost if latest_nav else None,
                latest_cumulative_return=cum_return,
                latest_return_rate=latest_nav.cum_return_rate if latest_nav else None,
            )
        )
    return result


@router.post("", response_model=PortfolioDetail, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    req: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建一个新的空投资组合。

    流程:
      1. 调用 generate_portfolio_code 生成唯一的 6 位组合代码
      2. 创建 Portfolio 记录，关联到当前用户
      3. 返回新组合的详情（初始无持仓、无 NAV）

    返回状态码: 201 Created
    """
    # 生成不重复的 6 位组合代码（如 "A3F8K2"）
    code = generate_portfolio_code(db)
    portfolio = Portfolio(
        user_id=current_user.id,
        name=req.name,
        code=code,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    # 新组合无持仓无净值，直接构造返回
    return PortfolioDetail(
        code=portfolio.code,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        return_start_date=portfolio.return_start_date,
        holdings=[],
        latest_nav=None,
        latest_total_cost=None,
        latest_cumulative_return=None,
        latest_return_rate=None,
    )


@router.get("/{code}", response_model=PortfolioDetail)
def get_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取单个组合的完整详情，包含持仓列表。

    返回内容:
      - 组合基本信息
      - 最新净值（NAV）及累计收益
      - 持仓明细列表，每只股票包含:
          * 当前市价（最新收盘价）
          * 持仓收益金额 = (当前价 - 成本价) × 持股数
          * 持仓收益率   = (当前价 / 成本价) - 1
          * 当日涨跌幅   = (今日收盘 - 昨日收盘) / 昨日收盘

    注意:
      - 成本价为 None 的持仓不计算收益（无成本基准）
      - 当日涨跌幅需要最近两个交易日的数据，不足两条则不计算
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    # 查询最新净值记录
    latest_nav = (
        db.query(PortfolioNavHistory)
        .filter(PortfolioNavHistory.portfolio_id == portfolio.id)
        .order_by(PortfolioNavHistory.nav_date.desc())
        .first()
    )

    # 便捷计算（前端也可完成）：累计收益 = 总市值 - 总成本
    cum_return = None
    if latest_nav and latest_nav.total_cost and latest_nav.total_cost > 0:
        cum_return = latest_nav.total_market_value - latest_nav.total_cost

    # 遍历每只持仓，计算个股维度的收益数据
    holdings = []
    for h in portfolio.holdings:
        # 获取该股票的最新收盘价（从日 K 线表取最新一条）
        current_price = get_latest_close(h.stock_id, db)

        # 便捷计算（前端也可完成）：持仓收益 = (现价 - 成本价) × 股数，拿到 current_price/cost_price/shares 即可算
        return_amount = None
        return_rate = None
        if h.cost_price is not None and current_price is not None and h.cost_price > 0:
            return_amount = (current_price - h.cost_price) * h.shares
            return_rate = (current_price / h.cost_price) - 1

        # 便捷计算（前端也可完成）：个股当日收益率 = (今收 - 昨收) / 昨收
        # 后端提供 prev_close 原始数据，前端拿到 current_price + prev_close 即可自行计算
        daily_return_rate = None
        prev_close = None
        latest_two = (
            db.query(DailyKline)
            .filter(DailyKline.stock_id == h.stock_id)
            .order_by(DailyKline.trade_date.desc())
            .limit(2)
            .all()
        )
        if len(latest_two) == 2 and latest_two[1].close > 0:
            daily_return_rate = (latest_two[0].close - latest_two[1].close) / latest_two[1].close
            prev_close = latest_two[1].close

        holdings.append(
            HoldingResponse(
                id=h.id,
                stock_code=h.stock.code,
                stock_name=h.stock.name,
                shares=h.shares,
                cost_price=h.cost_price,
                cost_price_set_at=h.cost_price_set_at,
                is_cost_locked=h.is_cost_locked,
                current_price=current_price,
                prev_close=prev_close,
                daily_return_rate=daily_return_rate,
                return_amount=return_amount,
                return_rate=return_rate,
            )
        )

    return PortfolioDetail(
        code=portfolio.code,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        return_start_date=portfolio.return_start_date,
        holdings=holdings,
        latest_nav=latest_nav.nav if latest_nav else None,
        latest_total_cost=latest_nav.total_cost if latest_nav else None,
        latest_cumulative_return=cum_return,
        latest_return_rate=latest_nav.cum_return_rate if latest_nav else None,
    )


@router.put("/{code}", response_model=PortfolioDetail)
def update_portfolio(
    code: str,
    req: PortfolioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新组合名称。

    仅修改 name 字段，持仓和净值数据不受影响。
    返回更新后的完整组合详情（复用 get_portfolio 逻辑）。
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    portfolio.name = req.name
    db.commit()
    db.refresh(portfolio)

    # 直接复用详情接口返回完整数据
    return get_portfolio(code, db, current_user)


@router.delete("/{code}", status_code=status.HTTP_200_OK)
def delete_portfolio(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除组合及其所有关联数据。

    数据库设置了级联删除（cascade），删除 Portfolio 记录时：
      - 该组合下的所有持仓（PortfolioHolding）一并删除
      - 该组合的所有净值历史（PortfolioNavHistory）一并删除

    返回状态码: 200 OK（而非 204 No Content），附带删除确认信息。
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    db.delete(portfolio)
    db.commit()

    return {"message": "Portfolio deleted", "code": code}


# ══════════════════════════════════════════════════════════════════════
# 二、持仓管理（添加 / 修改 / 删除 / 成本价设定）
# ══════════════════════════════════════════════════════════════════════

@router.post("/{code}/holdings", status_code=status.HTTP_201_CREATED)
def add_holding(
    code: str,
    req: AddHoldingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    向组合中添加一只股票持仓。

    业务规则:
      1. 股票必须存在且处于活跃状态（is_active = 1）
      2. 同一股票不可重复添加（返回 409 Conflict 提示使用 PUT 修改股数）
      3. 添加时可指定成本价；若不指定，系统自动取该股票最近收盘价
      4. 成本价一旦设定后即锁定（is_cost_locked = True），不可再次自动覆盖

    返回状态码: 201 Created
    """
    # 校验组合归属
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    # 校验股票存在且活跃
    stock = (
        db.query(Stock)
        .filter(Stock.code == req.stock_code, Stock.is_active == 1)
        .first()
    )
    if not stock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")

    # 防止重复添加同一股票
    existing = (
        db.query(PortfolioHolding)
        .filter(
            PortfolioHolding.portfolio_id == portfolio.id,
            PortfolioHolding.stock_id == stock.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock already in portfolio. Use PUT to update shares.",
        )

    # 创建持仓记录
    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        stock_id=stock.id,
        shares=req.shares,
    )

    # 设定成本价：有传参则用传参，否则自动取最近收盘价
    set_holding_cost_price(holding, db, req.cost_price)

    db.add(holding)
    db.commit()
    db.refresh(holding)

    return {
        "id": holding.id,
        "stock_code": stock.code,
        "stock_name": stock.name,
        "shares": holding.shares,
        "cost_price": holding.cost_price,
        "cost_price_set_at": holding.cost_price_set_at,
        "is_cost_locked": holding.is_cost_locked,
    }


@router.put("/{code}/holdings/{holding_id}")
def update_holding(
    code: str,
    holding_id: int,
    req: UpdateHoldingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新持仓的持股数量。

    注意:
      - 仅修改 shares 字段，成本价保持不变
      - 不支持通过此接口修改股票（要换股票请删除后重新添加）
      - 先校验组合归属，再校验持仓归属（两层权限校验）
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    # 同时校验 holding_id 和 portfolio_id，防止跨组合操作
    holding = db.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == portfolio.id,
    ).first()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    holding.shares = req.shares
    db.commit()

    return {"message": "Holding updated", "id": holding.id, "shares": holding.shares}


@router.delete("/{code}/holdings/{holding_id}")
def remove_holding(
    code: str,
    holding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    从组合中移除一只持仓股票。

    删除的是持仓记录（PortfolioHolding），不影响股票主数据（Stock）。
    同样执行两层权限校验：组合归属 → 持仓归属。
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    holding = db.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == portfolio.id,
    ).first()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    db.delete(holding)
    db.commit()

    return {"message": "Holding removed", "id": holding_id}


@router.post("/{code}/holdings/{holding_id}/set-cost")
def set_cost(
    code: str,
    holding_id: int,
    req: SetCostPriceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    手动设定或覆盖持仓的成本价。

    业务规则:
      - 成本价一旦被锁定（is_cost_locked = True），则不可再修改
      - 首次添加持仓时自动设定的成本价会锁定
      - 若成本价已锁定仍尝试修改，返回 400 Bad Request
      - 此接口用于首次手动设定成本价（添加时未传成本价的情况）

    注意:
      - 成本价修改后，已有的 NAV 历史不会自动更新，需调用 recalc-nav 重算
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    holding = db.query(PortfolioHolding).filter(
        PortfolioHolding.id == holding_id,
        PortfolioHolding.portfolio_id == portfolio.id,
    ).first()
    if not holding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    # 成本价锁定时拒绝修改
    if holding.is_cost_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cost price is immutable once set.",
        )

    holding.cost_price = req.cost_price
    holding.cost_price_set_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Cost price set",
        "cost_price": holding.cost_price,
    }


# ══════════════════════════════════════════════════════════════════════
# 三、图表与分析（NAV 曲线 / 日收益 / 月收益 / 单股贡献）
# ══════════════════════════════════════════════════════════════════════

@router.get("/{code}/nav", response_model=NavHistoryResponse)
def get_nav_history(
    code: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取组合的 NAV（净值）历史，用于绘制收益曲线图。

    查询参数:
      start  — 起始日期（YYYY-MM-DD），可选，不传则从最早记录开始
      end    — 截止日期（YYYY-MM-DD），可选，不传则到最新记录为止

    返回的每条 NAV 记录包含:
      - date:               交易日期
      - nav:                当日净值（= 总市值 / 总份额，这里简化为总市值）
      - daily_return:       当日收益金额（nav - 前一日 nav）
      - daily_return_rate:  当日收益率（(nav - 前一日 nav) / 前一日 nav）
      - cum_return_rate:    累计收益率（(总市值 / 总成本) - 1）
      - total_cost:         总成本
      - total_market_value: 总市值

    注意:
      - 第一条记录的日收益为 None（无前一日数据可比较）
      - 日收益均为实时计算（派生字段），不依赖数据库持久化值
      - 若无总成本数据，累计收益率为 None
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    # 构建查询，支持可选的日期范围过滤
    query = db.query(PortfolioNavHistory).filter(
        PortfolioNavHistory.portfolio_id == portfolio.id
    )
    if start:
        query = query.filter(PortfolioNavHistory.nav_date >= date.fromisoformat(start))
    if end:
        query = query.filter(PortfolioNavHistory.nav_date <= date.fromisoformat(end))

    # 按日期升序排列，便于计算逐日收益
    history = query.order_by(PortfolioNavHistory.nav_date.asc()).all()

    # 便捷计算（前端也可完成）：遍历 NAV 记录计算日收益和累计收益率。前端拿到 [nav, total_cost] 序列即可算
    data = []
    prev_nav = None  # 前一日净值，用于计算日收益
    for h in history:
        # 日收益 = 当日净值 - 前一日净值
        daily_return = None
        daily_return_rate = None
        if prev_nav is not None and prev_nav > 0:
            daily_return = h.nav - prev_nav
            daily_return_rate = daily_return / prev_nav
        prev_nav = h.nav

        # 累计收益率 = (总市值 / 总成本) - 1
        cum_return_rate = None
        if h.total_cost and h.total_cost > 0:
            cum_return_rate = (h.total_market_value / h.total_cost) - 1

        data.append(
            NavHistoryItem(
                date=h.nav_date.isoformat(),
                nav=h.nav,
                daily_return=daily_return,
                daily_return_rate=daily_return_rate,
                cum_return_rate=cum_return_rate,
                total_cost=h.total_cost,
                total_market_value=h.total_market_value,
            )
        )

    return NavHistoryResponse(
        portfolio_code=portfolio.code,
        portfolio_name=portfolio.name,
        data=data,
    )


@router.get("/{code}/daily-returns", response_model=DailyReturnsResponse)
def get_daily_returns(
    code: str,
    year: int = Query(..., description="Year for calendar"),
    month: int | None = Query(None, description="Optional month filter (1-12)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取指定年/月的每日收益数据，用于前端日历热力图展示。

    查询参数:
      year  — 年份（必填），如 2025
      month — 月份（可选，1-12），不传则返回全年数据

    返回数据:
      每个交易日一条记录，包含当日收益金额和收益率。
      非交易日不在数据中，前端自行处理日历空白格。

    计算逻辑:
      - 日收益金额 = 当日 NAV - 前一日 NAV
      - 日收益率   = (当日 NAV - 前一日 NAV) / 前一日 NAV
      - 为计算第一天（如 1 月 1 日或当月首个交易日）的日收益，
        会额外查询目标范围之前最近一条 NAV 记录作为 "前一天" 基准
    """
    # 校验组合归属
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    # 根据是否传入月份确定日期范围
    if month is not None:
        import calendar
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]  # 当月最后一天（28/29/30/31）
        end_date = date(year, month, last_day)
    else:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

    # 查询目标范围内的 NAV 记录
    history = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date >= start_date,
            PortfolioNavHistory.nav_date <= end_date,
        )
        .order_by(PortfolioNavHistory.nav_date.asc())
        .all()
    )

    # 查询范围之前最近一条 NAV，作为第一天日收益的计算基准
    prev_nav = None
    last_before = (
        db.query(PortfolioNavHistory)
        .filter(
            PortfolioNavHistory.portfolio_id == portfolio.id,
            PortfolioNavHistory.nav_date < start_date,
        )
        .order_by(PortfolioNavHistory.nav_date.desc())
        .first()
    )
    if last_before:
        prev_nav = last_before.nav

    # 便捷计算（前端也可完成）：逐日计算收益，前端拿到 NAV 序列后相邻相减即可
    data = []
    for h in history:
        return_amount = None
        return_rate = None
        if prev_nav is not None and prev_nav > 0:
            return_amount = h.nav - prev_nav
            return_rate = return_amount / prev_nav
        prev_nav = h.nav  # 当前 NAV 成为下一天的 "前一天"
        data.append(
            DailyReturnItem(
                date=h.nav_date.isoformat(),
                return_amount=return_amount,
                return_rate=return_rate,
            )
        )

    return DailyReturnsResponse(
        portfolio_code=portfolio.code,
        year=year,
        month=month,
        data=data,
    )


@router.get("/{code}/monthly-returns", response_model=MonthlyReturnsResponse)
def get_monthly_returns(
    code: str,
    year: int = Query(..., description="Year for monthly aggregation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取指定年份的月度收益汇总。

    遍历 1-12 月，对每个月的 NAV 数据做首尾对比：
      - 月收益金额 = 月末 NAV - 月初 NAV
      - 月收益率   = (月末 NAV - 月初 NAV) / 月初 NAV

    与日收益接口不同，月收益使用月初首日和月末末日两条记录的 NAV 直接对比，
    而非逐日累加，因此反映的是该月的整体净值变化。

    注意:
      - 若某月无任何 NAV 记录（如新组合或停市月份），该月的收益为 None
      - 月初 NAV 为 0 时收益率也为 None（避免除零）
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    import calendar as cal_mod

    # 便捷计算（前端也可完成）：按月份聚合 NAV 序列，月收益 = 月末净值 - 月初净值
    data = []
    for month in range(1, 13):
        last_day = cal_mod.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # 查询该月所有 NAV 记录，按日期排序
        month_navs = (
            db.query(PortfolioNavHistory)
            .filter(
                PortfolioNavHistory.portfolio_id == portfolio.id,
                PortfolioNavHistory.nav_date >= start_date,
                PortfolioNavHistory.nav_date <= end_date,
            )
            .order_by(PortfolioNavHistory.nav_date.asc())
            .all()
        )

        return_amount = None
        return_rate = None

        if month_navs:
            # 月初首日 NAV vs 月末末日 NAV
            first_nav = month_navs[0].nav
            last_nav = month_navs[-1].nav
            if first_nav and first_nav > 0:
                return_amount = last_nav - first_nav
                return_rate = (last_nav - first_nav) / first_nav

        data.append(
            MonthlyReturnItem(
                month=month,
                return_amount=return_amount,
                return_rate=return_rate,
            )
        )

    return MonthlyReturnsResponse(
        portfolio_code=portfolio.code,
        year=year,
        data=data,
    )


@router.get("/{code}/holdings-kline", response_model=HoldingsKlineResponse)
def get_holdings_kline(
    code: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取组合持仓的原始 K 线数据，供前端自行计算 NAV 序列、日历收益、贡献分析。

    此端点仅返回原始数据（close 价格），不做任何衍生计算。
    前端拿到后可以：
      - 算 NAV 序列：对每日 Σ(close × shares)
      - 算日收益：相邻 NAV 相减
      - 算月收益：月末 NAV - 月初 NAV
      - 算贡献：个股在期间内的价格变化 × 股数
    """
    portfolio = _get_user_portfolio(code, db, current_user)

    holdings_data = []
    for h in portfolio.holdings:
        query = db.query(DailyKline).filter(DailyKline.stock_id == h.stock_id)
        if start:
            query = query.filter(DailyKline.trade_date >= date.fromisoformat(start))
        if end:
            query = query.filter(DailyKline.trade_date <= date.fromisoformat(end))
        klines = query.order_by(DailyKline.trade_date.asc()).all()

        holdings_data.append(
            HoldingKlineItem(
                stock_code=h.stock.code,
                stock_name=h.stock.name,
                shares=h.shares,
                cost_price=h.cost_price,
                kline=[KlinePoint(date=k.trade_date.isoformat(), close=k.close) for k in klines],
            )
        )

    return HoldingsKlineResponse(
        portfolio_code=portfolio.code,
        return_start_date=portfolio.return_start_date,
        holdings=holdings_data,
    )


@router.get("/{code}/contributions", response_model=ContributionResponse)
def get_contributions(
    code: str,
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取组合中各只股票的收益贡献分析。

    用途:
      分析在指定日期范围内，每只持仓股票对组合整体收益的贡献程度。
      前端可用于饼图或贡献排行榜展示。

    查询参数:
      start — 起始日期，可选，不传则从组合最早记录开始
      end   — 截止日期，可选，不传则到最新记录为止

    计算逻辑由 services/portfolio_service.py 中的 calculate_contributions 实现，
    核心思路是：对每只持仓，计算其在范围首末的市值变化，得出贡献金额和贡献比例。
    """
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.code == code, Portfolio.user_id == current_user.id)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None

    # 便捷计算（前端也可完成，但需跨表查个股K线，后端做更方便）：委托 service 层完成贡献计算
    items = calculate_contributions(portfolio, db, start_date, end_date)

    return ContributionResponse(
        portfolio_code=portfolio.code,
        start_date=start or "",
        end_date=end or "",
        data=items,
    )


# ══════════════════════════════════════════════════════════════════════
# 四、收益计算起始日
# ══════════════════════════════════════════════════════════════════════

@router.put("/{code}/return-start-date", response_model=PortfolioDetail)
def set_return_start_date(
    code: str,
    req: SetReturnStartDateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    设定组合的收益计算起始日期。

    业务含义:
      - 收益曲线和 NAV 重算只从此日期开始，之前的数据不考虑
      - 例如用户 2024 年建仓但想从 2025-01-01 开始看收益表现

    修改后不会自动触发 NAV 重算，需手动调用 recalc-nav 接口。
    """
    portfolio = _get_user_portfolio(code, db, current_user)
    portfolio.return_start_date = req.return_start_date
    db.commit()
    db.refresh(portfolio)
    return get_portfolio(code, db, current_user)


# ══════════════════════════════════════════════════════════════════════
# 五、组合数据刷新（爬取持仓股票的 K 线数据）
# ══════════════════════════════════════════════════════════════════════

@router.post("/{code}/refresh-data", response_model=PortfolioRefreshResponse)
def refresh_portfolio_data_full(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    全量刷新组合数据：重新爬取所有持仓股票的 K 线数据。

    适用场景:
      - 首次添加多只股票后，一次性拉取全部历史数据
      - 怀疑数据有遗漏或错误，需要全量重建

    实现:
      委托 refresh_portfolio_kline(overwrite=True)，
      对每只持仓股票调用爬虫，已存在的 K 线记录会被覆盖更新。
    """
    portfolio = _get_user_portfolio(code, db, current_user)
    result = refresh_portfolio_kline(portfolio, db, overwrite=True)
    result["message"] = (
        f"全量更新完成: 处理 {result['processed']}/{result['total_stocks']} 只股票, "
        f"更新 {result['total_affected']} 条记录"
    )
    return result


@router.post("/{code}/refresh-data/incr", response_model=PortfolioRefreshResponse)
def refresh_portfolio_data_incr(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    增量刷新组合数据：仅爬取缺失的 K 线数据。

    适用场景:
      - 日常更新，补充最新交易日数据
      - 新增持仓股票后，只拉这只新股的数据

    实现:
      委托 refresh_portfolio_kline(overwrite=False)，
      已存在的 K 线记录不做更新，仅填充空缺日期。
    """
    portfolio = _get_user_portfolio(code, db, current_user)
    result = refresh_portfolio_kline(portfolio, db, overwrite=False)
    result["message"] = (
        f"增量更新完成: 处理 {result['processed']}/{result['total_stocks']} 只股票, "
        f"新增 {result['total_affected']} 条记录"
    )
    return result


# ══════════════════════════════════════════════════════════════════════
# 六、NAV 净值重算
# ══════════════════════════════════════════════════════════════════════

@router.post("/{code}/recalc-nav", response_model=PortfolioNavRecalcResponse)
def recalc_portfolio_nav_full(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    全量 NAV 重算：删除 return_start_date 之后的所有 NAV 记录并重新计算。

    适用场景:
      - 修改了持仓成本价
      - 修改了收益起始日
      - 添加/删除了持仓
      - 数据出现不一致需要重建

    流程:
      1. 删除从 return_start_date 起的所有 PortraitNavHistory 记录
      2. 从 return_start_date 起逐日重新计算净值（基于持仓 × 当日收盘价）
      3. 返回生成的记录数量
    """
    portfolio = _get_user_portfolio(code, db, current_user)
    result = recalculate_portfolio_nav(portfolio, db)
    result["message"] = f"全量收益计算完成: 生成 {result['records_created']} 条收益记录"
    return result


@router.post("/{code}/recalc-nav/incr", response_model=PortfolioNavRecalcResponse)
def recalc_portfolio_nav_incr(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    增量 NAV 填充：找到最新 NAV 日期，补充缺失日期到今日。

    适用场景:
      - 每日定时任务或手动触发，补充最新交易日的净值数据
      - K 线数据已通过 refresh-data 更新后，补齐对应的 NAV

    实现:
      委托 fill_missing_nav，从已有最新 NAV 日期的下一天开始，
      逐日计算到当前日期，不删除已有记录。
    """
    portfolio = _get_user_portfolio(code, db, current_user)
    result = fill_missing_nav(portfolio, db)
    result["message"] = f"增量收益计算完成: 生成 {result['records_created']} 条收益记录"
    return result
