# 需求文档：股票模拟交易 Web 应用

## 目录

1. [需求总览](#1-需求总览)
2. [模块一：股票数据采集](#2-模块一股票数据采集)
3. [模块二：用户系统](#3-模块二用户系统)
4. [模块三：自选股](#4-模块三自选股)
5. [模块四：K线图表](#5-模块四k线图表)
6. [模块五：股票组合（核心）](#6-模块五股票组合核心)
7. [模块六：组合图表分析](#7-模块六组合图表分析)
8. [模块七：首页仪表盘](#8-模块七首页仪表盘)
10. [附录 A：API 清单](#10-附录aapi-清单)
11. [附录 B：数据库结构](#11-附录-b数据库结构)

---

## 1. 需求总览

| 编号 | 需求 | 优先级 | 状态 |
|------|------|--------|------|
| R1 | 每日 06:00 自动爬取 A 股列表 | P0 | ✅ 已实现 |
| R2 | 用户注册/登录，数据隔离 | P0 | ✅ 已实现 |
| R3 | 个人自选股管理 | P1 | ✅ 已实现 |
| R4 | 股票日 K 线图查看 | P1 | ✅ 已实现 |
| R5 | 创建/管理多个股票组合 | P0 | ✅ 已实现 |
| R6 | 组合净值每日 15:05 自动更新 | P0 | ✅ 已实现 |
| R7 | 组合收益率曲线、日历热力图 | P1 | ✅ 已实现 |
| R8 | 各股票对组合收益贡献分析 | P2 | ✅ 已实现 |

---

## 2. 模块一：股票数据采集

### R1 — 每日凌晨 6:00 自动爬取 A 股列表

**需求原文**：
> 每天凌晨 6 点可以爬取当天的 A 股股票列表（只需要股票代码和股票名称）

**实现方式**：

| 维度 | 说明 |
|------|------|
| 数据源 | 新浪财经 HTTP API（股票列表 + K 线），Tencent API 备用 |
| 股票列表接口 | `vip.stock.finance.sina.com.cn` → `Market_Center.getHQNodeData` |
| K 线接口 | `money.finance.sina.com.cn` → `CN_MarketData.getKLineData` |
| 调度 | APScheduler，cron 表达式 `hour=6, minute=0`，时区 Asia/Shanghai |
| 执行入口 | `backend/app/services/scheduler.py` → `_crawl_job()` |
| 爬取逻辑 | `backend/app/services/crawler.py` → `crawl_stock_list()` |
| 存储表 | `stocks`（code, exchange, name, is_active） |
| 增量策略 | 新股票 INSERT，已有股票比对 name 后 UPDATE |
| 日志记录 | `crawl_log` 表（crawl_type='stock_list'） |
| 重试机制 | `_http_get_json()` — 3 次指数退避重试（2s / 4s / 8s） |
| 备选方案 | `akshare` 库、东方财富 API（`push2.eastmoney.com`） |

**数据流**：
```
APScheduler (06:00 CST)
  → crawler.crawl_stock_list()
    → HTTP GET vip.stock.finance.sina.com.cn/.../Market_Center.getHQNodeData
      → 解析 JSON → [{code, name, exchange}]
        → SQLAlchemy UPSERT → stocks 表
          → 写入 crawl_log
```

**股票代码规范**：
- `6xxxxx` → 上海交易所 (SH)
- `0xxxxx` / `3xxxxx` → 深圳交易所 (SZ)
- `8xxxxx` / `4xxxxx` → 北京交易所 (BJ)

---

## 3. 模块二：用户系统

### R2 — 用户注册/登录，数据隔离

**需求原文**：
> 用户可以添加自选股票（用户只能看到自己的自选列表）
> 每个用户可以创建自己股票组合

**实现方式**：

| 维度 | 说明 |
|------|------|
| 认证方式 | JWT（无状态 Token），7 天有效期 |
| 密码存储 | bcrypt 哈希（passlib + bcrypt 4.0） |
| 前端路由守卫 | `router.beforeEach`：无 token → 重定向 `/login` |
| 后端鉴权 | `get_current_user` 依赖项，解析 JWT 中的 user_id |
| 数据隔离 | **所有查询均带 `user_id` 过滤**（自选、组合、持仓） |
| 存储表 | `users`（username, password_hash） |

**API**：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 注册 → 返回 JWT |
| `/api/auth/login` | POST | 登录 → 返回 JWT |
| `/api/auth/me` | GET | 获取当前用户信息 |

**数据隔离示例**：
```python
# 自选股查询 — 始终带 user_id
db.query(WatchlistItem).filter(WatchlistItem.user_id == current_user.id)

# 组合查询 — 始终带 user_id
db.query(Portfolio).filter(Portfolio.user_id == current_user.id)
```

---

## 4. 模块三：自选股

### R3 — 个人自选股管理

**需求原文**：
> 用户可以添加自选股票（用户只能看到自己的自选列表）

**实现方式**：

| 维度 | 说明 |
|------|------|
| 存储表 | `watchlist_items`（user_id, stock_id, added_at），UNIQUE(user_id, stock_id) |
| 添加 | `POST /api/watchlist/{code}` → 校验股票存在 + 不重复 |
| 删除 | `DELETE /api/watchlist/{code}` |
| 查看 | `GET /api/watchlist` → 返回列表 + 每只股票最新收盘价 |
| 最新价查询 | 从 `daily_kline` 取 `trade_date DESC LIMIT 1` |

**前端页面**：

| 页面 | 路由 | 功能 |
|------|------|------|
| 自选列表 | `/watchlist` | 表格显示代码、名称、交易所、最新价，支持删除和跳转 K 线 |

---

## 5. 模块四：K 线图表

### R4 — 股票日 K 线图查看

**需求原文**：
> 软件可以查看股票的每日 K 线图

**实现方式**：

| 维度 | 说明 |
|------|------|
| 数据策略 | **缓存优先**：K 线数据存入 `daily_kline` 表，查看时从 DB 读取 |
| 按需回退 | 若 DB 无数据 → `crawl_kline_on_demand()` 实时抓取并缓存 |
| 图表库 | ECharts 5 candlestick 系列 |
| 技术指标 | MA5 / MA10 / MA20 均线（前端 JS 计算） |
| 成交量 | 子图，红涨绿跌 |
| 交互 | DataZoom 缩放、tooltip 十字光标、日期范围切换 |

**API**：

| 端点 | 参数 | 返回 |
|------|------|------|
| `GET /api/stocks/{code}/kline` | `start`, `end` (YYYY-MM-DD) | `{code, name, data: [{date, open, high, low, close, volume, amount}]}` |

**前端页面**：

| 页面 | 路由 | 功能 |
|------|------|------|
| K 线图 | `/stocks/:code/kline` | 蜡烛图 + MA 均线 + 成交量 + 日期选择器（1月/3月/6月/1年/全部） |

**数据格式（ECharts candlestick）**：
```javascript
// ECharts 需要的格式：[open, close, low, high]
data: [[10.50, 10.70, 10.40, 10.80], ...]
```

---

## 6. 模块五：股票组合（核心）

这是项目的核心模块，以下逐条对应。

### R5.1 — 创建组合

**需求原文**：
> 每个用户可以创建自己股票组合，股票组合从自选股票中选取，需要自己取名称，自动生成组合代码

**实现方式**：

| 维度 | 说明 |
|------|------|
| 存储表 | `portfolios`（user_id, name, code） |
| 代码生成 | `PF{YYYYMMDD}{NNN}`，如 `PF20260624001` |
| 代码唯一性 | 按当天最大序号 +1，DB 层 UNIQUE 约束兜底 |
| 生成逻辑 | `backend/app/services/portfolio_service.py` → `generate_portfolio_code()` |

### R5.2 — 添加持仓

**需求原文**：
> 用户可以随时将股票添加股票组合时，需要从自选股票中选取，同时填入股数，也可以指定成本价

**实现方式**：

| 维度 | 说明 |
|------|------|
| 存储表 | `portfolio_holdings`（portfolio_id, stock_id, shares, cost_price） |
| UNIQUE | (portfolio_id, stock_id) — 同一组合不能重复添加同一股票 |
| 添加 API | `POST /api/portfolios/{code}/holdings` |
| 修改股数 | `PUT /api/portfolios/{code}/holdings/{id}` |
| 删除持仓 | `DELETE /api/portfolios/{code}/holdings/{id}` |

**注意**：添加持仓时股票来源不做硬限制（可以是任意 A 股，不强制来自自选）。前端可在交互层面引导用户从自选中选取。

### R5.3 — 成本价逻辑（关键业务规则）

**需求原文**：
> 成本价设定之后就不可变，默认下午 3 点前使用上一日收盘价，3 点后使用当日收盘价

**实现方式**：

```
用户添加持仓
  │
  ├─ 用户填写了 cost_price？
  │   └─ YES → 直接使用，写入 cost_price，设置 cost_price_set_at = NOW
  │            ✅ 此后不可修改（UI 隐藏编辑按钮 + API 层拒绝）
  │
  └─ NO → 判断当前 CST 时间
        │
        ├─ 当前时间 < 15:00
        │   → 查 daily_kline WHERE trade_date < today ORDER BY trade_date DESC LIMIT 1
        │   → 取该记录的 close 作为成本价
        │
        └─ 当前时间 >= 15:00
            → 查 daily_kline WHERE trade_date == today
            → 有数据？ → 取今日 close
            → 无数据（周末/节假日）？ → 取最近交易日 close
            → 完全没有 K 线数据？ → 返回错误，要求用户手动填写
```

**核心代码位置**：`backend/app/services/portfolio_service.py` → `set_holding_cost_price()`

**不可变保证**：
- **数据库层**：`cost_price` 列一旦写入非 NULL，API 层阻止 UPDATE
- **API 层**：`POST /.../set-cost` 检查 `holding.is_cost_locked`，已锁定返回 400
- **前端层**：成本价已设定时，隐藏"设定成本"按钮，显示"成本已锁定"标签

### R5.4 — 多组合支持

**需求原文**：
> 一个用户可以创建多个组合

**实现方式**：

- `portfolios` 表与 `users` 是一对多关系
- 用户可创建任意数量组合
- 列表页用卡片展示，每个卡片可点击进入详情

### R5.5 — 每日净值更新

**需求原文**：
> 每个组合每天下午 3 点 5 分更新净值

**实现方式**：

| 维度 | 说明 |
|------|------|
| 调度 | APScheduler，cron `hour=15, minute=5` |
| 执行入口 | `backend/app/services/scheduler.py` → `_nav_update_job()` |
| 计算逻辑 | `backend/app/services/portfolio_service.py` → `update_all_portfolios_nav()` |
| 存储表 | `portfolio_nav_history`（一天一条，UNIQUE(portfolio_id, nav_date)） |

**净值计算过程**：
```
对每个组合：
  对每个持仓：
    取该股票最新 close（从 daily_kline）
    market_value = shares × close
    如果 cost_price 已设定：
      cost_basis = shares × cost_price

  total_market_value = Σ market_value
  total_cost = Σ cost_basis

  nav = total_market_value

  取昨日 NAV 记录：
    daily_return = nav_today - nav_yesterday
    daily_return_rate = (nav_today - nav_yesterday) / nav_yesterday

  如果 total_cost > 0：
    cum_return_rate = (total_market_value / total_cost) - 1

  UPSERT → portfolio_nav_history
```

**边界情况处理**：
- 持仓股票今日无 K 线数据 → 使用最新可用 close，记录日志
- 组合首次计算（无昨日 NAV）→ daily_return 为 NULL
- 所有持仓均无成本价 → cum_return_rate 为 NULL
- 股票停牌 → 使用最近交易日数据

### R5.6 — 收益率定义

**需求原文**：
> 组合收益为组合净值减去组合成本，组合收益率 = （当日组合净值 / 组合成本） - 1

**实现方式**：

```python
# 单日收益率
daily_return_rate = (nav_today - nav_yesterday) / nav_yesterday

# 累计收益率
cum_return_rate = (total_market_value / total_cost) - 1
```

存储于 `portfolio_nav_history` 表 `daily_return_rate` 和 `cum_return_rate` 列。

---

## 7. 模块六：组合图表分析

### R7.1 — 收益曲线

**需求原文**：
> 需要记录每天收益率、组合净值、组合收益，方便展示收益曲线

**API**：`GET /api/portfolios/{code}/nav?start=&end=`

**前端**：ECharts 折线图，X 轴为日期，Y 轴为累计收益率（%），包含 0% 参考线和面积填充

### R7.2 — 收益日历

**需求原文**：
> 收益日历即每日组合收益变化

**API**：`GET /api/portfolios/{code}/daily-returns?year=`

**前端**：ECharts 日历热力图，每个格子代表一天，颜色表示收益率（红涨绿跌）

### R7.3 — 贡献分析

**需求原文**：
> 组合可以查看各个股票对收益的贡献图表，可以指定具体时间段筛选查看

**API**：`GET /api/portfolios/{code}/contributions?start=&end=`

**计算逻辑**（`calculate_contributions()`）：
```
对每个持仓：
  取区间起始日期的 close → start_price
  取区间结束日期的 close → end_price
  market_value = shares × end_price
  return_amount = (end_price - cost_price) × shares
  contribution_pct = return_amount / portfolio_total_cost
```

**前端**：ECharts 横向柱状图，Y 轴为股票名称，X 轴为收益金额，红涨绿跌

**图表汇总**：

| 图表 | 前端组件 | 路由位置 |
|------|----------|----------|
| 收益曲线 | ECharts line + area | `/portfolios/:code` → 收益曲线 Tab |
| 收益日历 | ECharts calendar heatmap | `/portfolios/:code` → 收益日历 Tab |
| 贡献分析 | ECharts horizontal bar | `/portfolios/:code` → 贡献分析 Tab |

每个图表支持：
- 日期范围筛选（曲线：1月/3月/6月/1年/全部）
- 年份切换（日历热力图）
- Tooltip 数值提示

---

## 8. 模块七：首页仪表盘

**路由**：`/`

**功能**：
- 显示用户名
- 统计卡片：自选股数量、组合数量、A 股总数
- 快捷操作：搜索股票、创建组合、查看自选

---

## 9. 附录 A：API 清单

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户 |

### 股票

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks?q=` | 搜索（代码/名称） |
| GET | `/api/stocks/{code}` | 股票详情 |
| GET | `/api/stocks/{code}/kline?start=&end=` | K 线数据 |

### 自选

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/watchlist` | 我的自选 |
| POST | `/api/watchlist/{code}` | 添加自选 |
| DELETE | `/api/watchlist/{code}` | 删除自选 |

### 组合

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/portfolios` | 我的组合列表 |
| POST | `/api/portfolios` | 创建组合 |
| GET | `/api/portfolios/{code}` | 组合详情 + 持仓 |
| PUT | `/api/portfolios/{code}` | 修改名称 |
| DELETE | `/api/portfolios/{code}` | 删除组合 |
| POST | `/api/portfolios/{code}/holdings` | 添加持仓 |
| PUT | `/api/portfolios/{code}/holdings/{id}` | 修改股数 |
| DELETE | `/api/portfolios/{code}/holdings/{id}` | 删除持仓 |
| POST | `/api/portfolios/{code}/holdings/{id}/set-cost` | 设定成本价 |

### 分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/portfolios/{code}/nav?start=&end=` | 净值历史（收益曲线） |
| GET | `/api/portfolios/{code}/daily-returns?year=` | 每日收益率（热力图） |
| GET | `/api/portfolios/{code}/contributions?start=&end=` | 贡献分析 |

---

## 10. 附录 B：数据库结构

### 10.1 实体关系图 (ER)

```
users (1) ────── (N) watchlist_items (N) ────── (1) stocks (1) ────── (N) daily_kline
users (1) ────── (N) portfolios (1) ────── (N) portfolio_holdings (N) ────── (1) stocks
portfolios (1) ────── (N) portfolio_nav_history
```

**关系说明**：

| 关系 | 类型 | 说明 |
|------|------|------|
| users → watchlist_items | 1:N | 一个用户有多个自选股 |
| stocks → watchlist_items | 1:N | 一只股票可被多个用户添加为自选 |
| users → portfolios | 1:N | 一个用户可创建多个组合 |
| portfolios → portfolio_holdings | 1:N | 一个组合包含多个持仓 |
| stocks → portfolio_holdings | 1:N | 一只股票可被多个组合持有 |
| portfolios → portfolio_nav_history | 1:N | 一个组合每天产生一条净值记录 |
| stocks → daily_kline | 1:N | 一只股票每天产生一条K线记录 |

### 10.2 表结构详细说明

#### 表 1: `users` — 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | 用户唯一标识 |
| `username` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | 登录用户名 |
| `password_hash` | VARCHAR(256) | NOT NULL | bcrypt 哈希密码 |
| `created_at` | DATETIME | NOT NULL, DEFAULT NOW() | 注册时间 |

```sql
CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
);
```

#### 表 2: `stocks` — A 股股票主表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | 内部 ID |
| `code` | VARCHAR(6) | UNIQUE, NOT NULL, INDEX | 股票代码，如 `600519` |
| `exchange` | ENUM('SH','SZ','BJ') | NOT NULL | 交易所：上海/深圳/北京 |
| `name` | VARCHAR(64) | NOT NULL | 股票中文名称 |
| `is_active` | TINYINT(1) | NOT NULL, DEFAULT 1 | 是否活跃（0=已退市） |
| `created_at` | DATETIME | NOT NULL, DEFAULT NOW() | 首次入库时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE NOW() | 最后更新时间 |

```sql
CREATE TABLE stocks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(6)   NOT NULL UNIQUE,
    exchange        ENUM('SH','SZ','BJ') NOT NULL,
    name            VARCHAR(64)  NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_code (code)
);
```

**交易所代码规则**：

| 前缀 | 交易所 | exchange 值 |
|------|--------|-------------|
| `6xxxxx` | 上海证券交易所 | `SH` |
| `0xxxxx`, `3xxxxx` | 深圳证券交易所 | `SZ` |
| `4xxxxx`, `8xxxxx` | 北京证券交易所 | `BJ` |

#### 表 3: `daily_kline` — 日 K 线数据

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | — |
| `stock_id` | INT | FK → stocks.id, NOT NULL, INDEX | 关联股票 |
| `trade_date` | DATE | NOT NULL | 交易日期 |
| `open` | DECIMAL(10,3) | NOT NULL | 开盘价 |
| `high` | DECIMAL(10,3) | NOT NULL | 最高价 |
| `low` | DECIMAL(10,3) | NOT NULL | 最低价 |
| `close` | DECIMAL(10,3) | NOT NULL | 收盘价 |
| `volume` | BIGINT | NOT NULL | 成交量（股数） |
| `amount` | DECIMAL(18,2) | NOT NULL | 成交额（元） |

**唯一约束**：`UNIQUE (stock_id, trade_date)` — 一只股票每天只有一条记录

```sql
CREATE TABLE daily_kline (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    stock_id        INT           NOT NULL,
    trade_date      DATE          NOT NULL,
    open            DECIMAL(10,3) NOT NULL,
    high            DECIMAL(10,3) NOT NULL,
    low             DECIMAL(10,3) NOT NULL,
    close           DECIMAL(10,3) NOT NULL,
    volume          BIGINT        NOT NULL,
    amount          DECIMAL(18,2) NOT NULL,
    UNIQUE KEY uk_stock_date (stock_id, trade_date),
    INDEX idx_stock_date (stock_id, trade_date),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
);
```

**数据估算**：
- A 股总数约 5,500 只
- 每只股票每年约 250 个交易日
- 10 年数据：5,500 × 250 × 10 ≈ 1,375 万条记录
- 单条记录约 80 字节 → 总数据量约 1.1 GB（不含索引）
- 加上索引约 1.7 GB

#### 表 4: `watchlist_items` — 用户自选股

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | — |
| `user_id` | INT | FK → users.id, NOT NULL, INDEX | 用户 |
| `stock_id` | INT | FK → stocks.id, NOT NULL | 股票 |
| `added_at` | DATETIME | NOT NULL, DEFAULT NOW() | 添加时间 |

**唯一约束**：`UNIQUE (user_id, stock_id)` — 同一用户不能重复添加同一股票

```sql
CREATE TABLE watchlist_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT      NOT NULL,
    stock_id        INT      NOT NULL,
    added_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_stock (user_id, stock_id),
    INDEX idx_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
);
```

#### 表 5: `portfolios` — 股票组合

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | 内部 ID |
| `user_id` | INT | FK → users.id, NOT NULL, INDEX | 所属用户 |
| `name` | VARCHAR(128) | NOT NULL | 组合名称（用户自定义） |
| `code` | VARCHAR(20) | UNIQUE, NOT NULL | 系统自动生成，如 `PF20260624001` |
| `created_at` | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE NOW() | 最后修改时间 |

```sql
CREATE TABLE portfolios (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    name            VARCHAR(128) NOT NULL,
    code            VARCHAR(20)  NOT NULL UNIQUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**组合代码生成规则**：

```
PF{YYYYMMDD}{NNN}

- PF：固定前缀
- YYYYMMDD：创建日期
- NNN：当日序号，从 001 开始递增

示例：2026 年 6 月 24 日创建的第 1 个组合 → PF20260624001
      同一天创建的第 2 个组合         → PF20260624002
```

代码生成逻辑位于 `backend/app/services/portfolio_service.py` → `generate_portfolio_code()`。

#### 表 6: `portfolio_holdings` — 组合持仓

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | — |
| `portfolio_id` | INT | FK → portfolios.id ON DELETE CASCADE, NOT NULL, INDEX | 所属组合 |
| `stock_id` | INT | FK → stocks.id, NOT NULL | 股票 |
| `shares` | DECIMAL(10,2) | NOT NULL | 持有股数 |
| `cost_price` | DECIMAL(10,3) | NULL | 成本价（NULL=未设定） |
| `cost_price_set_at` | DATETIME | NULL | 成本价设定时间 |
| `created_at` | DATETIME | NOT NULL, DEFAULT NOW() | 添加时间 |

**唯一约束**：`UNIQUE (portfolio_id, stock_id)` — 同一组合不能重复持有同一股票

**关键设计**：
- `cost_price` 默认为 NULL，表示"尚未设定"
- 一旦写入非 NULL 值 → **此后不可修改**（业务层强制）
- `cost_price_set_at` 记录设定时间，用于审计追溯
- 删除组合时级联删除 (`ON DELETE CASCADE`)

```sql
CREATE TABLE portfolio_holdings (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id      INT            NOT NULL,
    stock_id          INT            NOT NULL,
    shares            DECIMAL(10,2)  NOT NULL,
    cost_price        DECIMAL(10,3)  NULL,
    cost_price_set_at DATETIME       NULL,
    created_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_portfolio_stock (portfolio_id, stock_id),
    INDEX idx_portfolio (portfolio_id),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
);
```

#### 表 7: `portfolio_nav_history` — 组合净值历史

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | — |
| `portfolio_id` | INT | FK → portfolios.id ON DELETE CASCADE, NOT NULL, INDEX | 所属组合 |
| `nav_date` | DATE | NOT NULL | 净值日期 |
| `nav` | DECIMAL(18,3) | NOT NULL | 当日净值（= 总市值） |
| `daily_return` | DECIMAL(18,3) | NULL | 日收益额（nav - 昨日nav） |
| `daily_return_rate` | DECIMAL(10,6) | NULL | 日收益率（(nav/昨日nav) - 1） |
| `cum_return_rate` | DECIMAL(10,6) | NULL | 累计收益率（(nav/total_cost) - 1） |
| `total_cost` | DECIMAL(18,3) | NOT NULL, DEFAULT 0 | 总成本（Σ shares × cost_price） |
| `total_market_value` | DECIMAL(18,3) | NOT NULL, DEFAULT 0 | 总市值（Σ shares × close） |
| `created_at` | DATETIME | NOT NULL, DEFAULT NOW() | 记录时间 |

**唯一约束**：`UNIQUE (portfolio_id, nav_date)` — 每个组合每天一条记录

```sql
CREATE TABLE portfolio_nav_history (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id        INT            NOT NULL,
    nav_date            DATE           NOT NULL,
    nav                 DECIMAL(18,3)  NOT NULL,
    daily_return        DECIMAL(18,3)  NULL,
    daily_return_rate   DECIMAL(10,6)  NULL,
    cum_return_rate     DECIMAL(10,6)  NULL,
    total_cost          DECIMAL(18,3)  NOT NULL DEFAULT 0,
    total_market_value  DECIMAL(18,3)  NOT NULL DEFAULT 0,
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_portfolio_date (portfolio_id, nav_date),
    INDEX idx_portfolio_date (portfolio_id, nav_date),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
);
```

**可空字段说明**：

| 字段 | 何时为 NULL |
|------|-------------|
| `daily_return`, `daily_return_rate` | 组合首次计算净值时无昨日数据 |
| `cum_return_rate` | 所有持仓的 `cost_price` 均未设定 |

#### 表 8: `crawl_log` — 数据爬取日志

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AUTO_INCREMENT | — |
| `crawl_type` | VARCHAR(32) | NOT NULL, INDEX | 爬取类型：`stock_list` / `daily_kline` |
| `ref_date` | DATE | NOT NULL | 爬取目标日期 |
| `status` | VARCHAR(16) | NOT NULL | 状态：`success` / `partial` / `failed` |
| `details` | JSON | NULL | 详细结果（新增/更新数量、错误信息等） |
| `created_at` | DATETIME | NOT NULL, DEFAULT NOW() | 记录时间 |

```sql
CREATE TABLE crawl_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    crawl_type      VARCHAR(32)  NOT NULL,
    ref_date        DATE         NOT NULL,
    status          VARCHAR(16)  NOT NULL,
    details         JSON         NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type_date (crawl_type, ref_date)
);
```

### 10.3 关键业务约束

#### 成本价不可变

```
portfolio_holdings.cost_price
  │
  ├─ 初始状态：NULL
  │
  ├─ 首次设定（用户提供 或 系统自动计算）
  │   └─ 写入 cost_price + cost_price_set_at
  │       └─ 🚫 之后任何 UPDATE 被拒绝
  │
  └─ 保护层级：
      ├─ API 层：holding.is_cost_locked → True → 返回 400
      └─ 前端层：按钮隐藏 + "成本已锁定" 标签
```

#### 唯一性约束汇总

| 表 | 唯一约束 | 含义 |
|----|----------|------|
| `users` | `UNIQUE(username)` | 用户名不可重复 |
| `stocks` | `UNIQUE(code)` | 股票代码不可重复 |
| `daily_kline` | `UNIQUE(stock_id, trade_date)` | 每只股票每天一条 K 线 |
| `watchlist_items` | `UNIQUE(user_id, stock_id)` | 同一用户不重复自选 |
| `portfolios` | `UNIQUE(code)` | 组合代码全局唯一 |
| `portfolio_holdings` | `UNIQUE(portfolio_id, stock_id)` | 同一组合不重复持仓 |
| `portfolio_nav_history` | `UNIQUE(portfolio_id, nav_date)` | 每个组合每天一条净值 |

#### 级联删除

| 外键 | ON DELETE | 效果 |
|------|-----------|------|
| `portfolio_holdings.portfolio_id` | `CASCADE` | 删除组合 → 自动删除所有持仓 |
| `portfolio_nav_history.portfolio_id` | `CASCADE` | 删除组合 → 自动删除所有净值历史 |

### 10.4 实体关系 SQL（完整 DDL）

<details>
<summary>点击展开完整建表 SQL</summary>

```sql
-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. 股票主表
-- ============================================================
CREATE TABLE stocks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(6)   NOT NULL UNIQUE,
    exchange        ENUM('SH','SZ','BJ') NOT NULL,
    name            VARCHAR(64)  NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. 日 K 线表
-- ============================================================
CREATE TABLE daily_kline (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    stock_id        INT           NOT NULL,
    trade_date      DATE          NOT NULL,
    open            DECIMAL(10,3) NOT NULL,
    high            DECIMAL(10,3) NOT NULL,
    low             DECIMAL(10,3) NOT NULL,
    close           DECIMAL(10,3) NOT NULL,
    volume          BIGINT        NOT NULL,
    amount          DECIMAL(18,2) NOT NULL,
    UNIQUE KEY uk_stock_date (stock_id, trade_date),
    INDEX idx_stock_date (stock_id, trade_date),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. 自选股表
-- ============================================================
CREATE TABLE watchlist_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT      NOT NULL,
    stock_id        INT      NOT NULL,
    added_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_stock (user_id, stock_id),
    INDEX idx_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. 组合表
-- ============================================================
CREATE TABLE portfolios (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    name            VARCHAR(128) NOT NULL,
    code            VARCHAR(20)  NOT NULL UNIQUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. 组合持仓表
-- ============================================================
CREATE TABLE portfolio_holdings (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id      INT            NOT NULL,
    stock_id          INT            NOT NULL,
    shares            DECIMAL(10,2)  NOT NULL,
    cost_price        DECIMAL(10,3)  NULL,
    cost_price_set_at DATETIME       NULL,
    created_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_portfolio_stock (portfolio_id, stock_id),
    INDEX idx_portfolio (portfolio_id),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 7. 组合净值历史表
-- ============================================================
CREATE TABLE portfolio_nav_history (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id        INT            NOT NULL,
    nav_date            DATE           NOT NULL,
    nav                 DECIMAL(18,3)  NOT NULL,
    daily_return        DECIMAL(18,3)  NULL,
    daily_return_rate   DECIMAL(10,6)  NULL,
    cum_return_rate     DECIMAL(10,6)  NULL,
    total_cost          DECIMAL(18,3)  NOT NULL DEFAULT 0,
    total_market_value  DECIMAL(18,3)  NOT NULL DEFAULT 0,
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_portfolio_date (portfolio_id, nav_date),
    INDEX idx_portfolio_date (portfolio_id, nav_date),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 8. 爬取日志表
-- ============================================================
CREATE TABLE crawl_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    crawl_type      VARCHAR(32)  NOT NULL,
    ref_date        DATE         NOT NULL,
    status          VARCHAR(16)  NOT NULL,
    details         JSON         NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type_date (crawl_type, ref_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

</details>

### 10.5 数据流示意

#### 净值计算流程

```
APScheduler @ 15:05 CST
  │
  ▼
对每个 Portfolio：
  │
  ├─ 遍历 portfolio_holdings
  │   │
  │   ├─ 查 daily_kline 取每个 stock 的最新 close
  │   ├─ market_value = shares × close
  │   └─ cost_basis   = shares × cost_price (如果有)
  │
  ├─ nav = Σ market_value
  ├─ total_cost = Σ cost_basis
  │
  ├─ 查 portfolio_nav_history 取昨日记录
  │   ├─ daily_return = nav - yesterday_nav
  │   └─ daily_return_rate = daily_return / yesterday_nav
  │
  ├─ cum_return_rate = (nav / total_cost) - 1
  │
  └─ UPSERT → portfolio_nav_history
```

#### 成本价设定流程

```
POST /api/portfolios/{code}/holdings
  │
  ├─ 用户传了 cost_price？
  │   └─ YES → 直接写入，锁定
  │
  └─ NO → 自动计算
        │
        ├─ 当前 CST < 15:00 → 取上一交易日 close
        └─ 当前 CST ≥ 15:00 → 取当日 close（回退到最近交易日）
```
