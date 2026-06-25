# Stock Simulation Web Application - Architecture Document

## Overview

A multi-user A-share stock simulation web application with personal watchlists, daily K-line charts, and portfolio management with NAV tracking and performance analytics.

## Architecture Diagram

```
┌──────────────────────────────────────────────────┐
│                    Nginx                          │
│         /           → 前端静态文件 (frontend/dist/)  │
│         /api/*      → proxy_pass :8000            │
└──────────┬───────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌──────────┐  ┌──────────────────────────────┐
│  Frontend │  │         Backend              │
│           │  │                              │
│ Vite 构建  │  │  FastAPI (uvicorn)           │
│ Vue 3 SFC │  │  ├── SQLAlchemy 2.0 (ORM)    │
│ Vue Router│  │  ├── MySQL 8.0               │
│ ECharts 5 │  │  ├── APScheduler             │
│ Axios     │  │  ├── JWT Auth                │
│ Pinia     │  │  ├── Sina Finance (数据源)   │
│           │  │  └── Alembic (迁移)          │
│           │  │                              │
│ 纯静态文件  │  │  Pure JSON REST API          │
└──────────┘  └──────────────────────────────┘
```

## Technology Stack

### Frontend
| Component | Choice | Purpose |
|-----------|--------|---------|
| Build | Vite 5 | Dev server with HMR, production bundling |
| Framework | Vue 3 (Composition API) | Reactive SPA framework |
| Router | Vue Router 4 | Client-side routing |
| State | Pinia | Auth state, portfolio state |
| HTTP | Axios | API calls with JWT interceptors |
| Charts | ECharts 5 | Candlestick, line, heatmap charts |
| UI | Element Plus | Vue 3 component library |
| CSS | Element Plus built-in | Consistent design system |

### Backend
| Component | Choice | Purpose |
|-----------|--------|---------|
| Framework | FastAPI | REST API with auto OpenAPI docs |
| ORM | SQLAlchemy 2.0 | Database abstraction |
| Database | MySQL 8.0 | Production-grade RDBMS |
| Migration | Alembic | Schema versioning |
| Auth | JWT (python-jose) | Stateless authentication |
| Password | passlib + bcrypt | Secure password hashing |
| Scheduler | APScheduler | Cron jobs (06:00 crawl, 15:05 NAV) |
| Data | Sina Finance API | Free A-share data (stock list + daily K-line) |
| Server | uvicorn + gunicorn | ASGI multi-process serving |

### Deployment
| Component | Choice |
|-----------|--------|
| Reverse Proxy | Nginx |
| WSGI/ASGI | gunicorn + uvicorn workers |
| Process Manager | systemd |
| Database Server | MySQL 8.0 |

## Project Structure

```
stock_web/
├── frontend/                    # Vue 3 SPA
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/index.js
│   │   ├── stores/              # Pinia stores
│   │   ├── api/index.js         # Axios + interceptors
│   │   ├── views/               # Route-level pages
│   │   ├── components/          # Reusable components
│   │   └── utils/               # Formatters, portfolioCalc.js
│   └── dist/                    # Production build
├── backend/                     # FastAPI
│   ├── app/
│   │   ├── main.py              # App entry point
│   │   ├── config.py            # Settings
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # ORM models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API routes
│   │   ├── services/            # Business logic
│   │   └── utils/               # Helpers
│   ├── alembic/                 # DB migrations
│   ├── alembic.ini
│   ├── requirements.txt
│   └── cli.py                   # Manual crawl CLI
├── nginx/
│   └── stock-web.conf
├── app.sh                     # 统一管理脚本
└── README.md
```

## Database Schema

```
users (1) ────── (N) watchlist_items (N) ────── (1) stocks (1) ────── (N) daily_kline
users (1) ────── (N) portfolios (1) ────── (N) portfolio_holdings (N) ────── (1) stocks
portfolios (1) ────── (N) portfolio_nav_history

market_index      — standalone daily snapshots
market_breadth    — standalone daily snapshots (per board)
sector_data       — standalone daily snapshots
```

### Tables

- **users**: id, username, password_hash, created_at
- **stocks**: id, code (VARCHAR 6, UNIQUE), exchange (ENUM SH/SZ/BJ), name, is_active
- **daily_kline**: stock_id, trade_date (DATE), open, high, low, close, volume, amount; UNIQUE(stock_id, trade_date)
- **watchlist_items**: user_id, stock_id, added_at; UNIQUE(user_id, stock_id)
- **portfolios**: user_id, name, code (VARCHAR 20, UNIQUE, auto-generated PFYYYYMMDDNNN)
- **portfolio_holdings**: portfolio_id, stock_id, shares, cost_price (nullable, immutable), cost_price_set_at
- **portfolio_nav_history**: portfolio_id, nav_date, nav, daily_return, daily_return_rate, cum_return_rate, total_cost, total_market_value
- **crawl_log**: crawl_type, ref_date, status, details (JSON)
- **market_index**: code, name, trade_date, open/high/low/close, change, change_pct; UNIQUE(code, trade_date)
- **market_breadth**: board, trade_date, total, up_count, down_count, flat_count; UNIQUE(board, trade_date)
- **sector_data**: code, name, trade_date, change_pct, leading_stock, rank; UNIQUE(code, trade_date)

## API Design

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /api/auth/register | No | Register |
| POST | /api/auth/login | No | Login → JWT |
| GET | /api/auth/me | Yes | Current user |
| GET | /api/stocks/count | Yes | Total active stock count |
| GET | /api/stocks | Yes | Search stocks |
| GET | /api/stocks/{code} | Yes | Stock detail |
| GET | /api/stocks/{code}/kline | Yes | K-line data |
| GET | /api/market/indices | Yes | Major index quotes |
| GET | /api/market/breadth | Yes | Market up/down counts |
| GET | /api/market/sectors | Yes | Sector ranking |
| GET | /api/watchlist | Yes | My watchlist |
| POST | /api/watchlist/{code} | Yes | Add to watchlist |
| DELETE | /api/watchlist/{code} | Yes | Remove from watchlist |
| GET | /api/portfolios | Yes | My portfolios |
| POST | /api/portfolios | Yes | Create portfolio |
| GET | /api/portfolios/{code} | Yes | Portfolio detail |
| PUT | /api/portfolios/{code} | Yes | Update portfolio |
| DELETE | /api/portfolios/{code} | Yes | Delete portfolio |
| POST | /api/portfolios/{code}/holdings | Yes | Add holding |
| PUT | /api/portfolios/{code}/holdings/{id} | Yes | Update holding |
| DELETE | /api/portfolios/{code}/holdings/{id} | Yes | Remove holding |
| POST | /api/portfolios/{code}/holdings/{id}/set-cost | Yes | Set cost price |
| GET | /api/portfolios/{code}/nav | Yes | NAV history |
| GET | /api/portfolios/{code}/daily-returns | Yes | Daily returns |
| GET | /api/portfolios/{code}/monthly-returns | Yes | Monthly returns |
| GET | /api/portfolios/{code}/contributions | Yes | Contribution |

## Key Business Rules

### Cost Price Logic
- User can provide cost_price explicitly → set and lock immediately
- User omits cost_price:
  - Before 15:00 CST → use previous trading day close
  - After 15:00 CST → use today's close (fallback to previous if no data)
- Once set, cost_price is immutable

### Portfolio NAV Update (daily 15:05 CST)
- For each portfolio holding: market_value = shares × today_close
- total_market_value = sum of all holding market values
- total_cost = sum of holdings with cost_price set
- cum_return_rate = (total_market_value / total_cost) - 1
- daily_return_rate = (nav_today - nav_yesterday) / nav_yesterday

### Portfolio Code Generation
- Pattern: `PF{YYYYMMDD}{NNN}` (e.g., PF20260624001)
- Sequence resets daily, pads to 3 digits

## Frontend Computation (前端计算方案)

为减轻后端计算压力，组合详情页（PortfolioDetail）的衍生指标计算已迁移到前端。
后端负责提供原始数据，前端利用 `frontend/src/utils/portfolioCalc.js` 工具库自行计算。

### 数据流

```
后端接口                         原始数据                       前端计算
──────────────────────────────────────────────────────────────────────
GET /portfolios/{code}
  ├─ latest_nav          ──→  calcCumReturn()         ──→  Hero 累计收益
  ├─ latest_total_cost   ──→  calcReturnRate()        ──→  Hero 累计收益率
  ├─ holdings[].current_price
  │  holdings[].cost_price
  │  holdings[].shares    ──→  calcReturnAmount()     ──→  持仓累计收益
  │                       ──→  calcReturnRate()       ──→  持仓收益率
  ├─ holdings[].current_price
  │  holdings[].prev_close──→  calcDailyReturnRate()  ──→  持仓当日收益率
  │
GET /portfolios/{code}/nav
  └─ data[].nav + date   ──→  calcDailyReturns()     ──→  日历日收益
                          ──→  calcMonthlyReturns()   ──→  日历月收益

GET /portfolios/{code}/contributions
  └─ 跨表查个股K线，前端不便，保留后端计算
```

### 前端计算工具库

**文件**: `frontend/src/utils/portfolioCalc.js`

| 函数 | 输入 | 输出 | 替代后端 |
|------|------|------|---------|
| `calcReturnAmount(cur, cost, shares)` | 现价、成本价、股数 | 持仓收益金额 | 后端 `return_amount` |
| `calcReturnRate(cur, cost)` | 现价、成本价 | 持仓收益率 | 后端 `return_rate` |
| `calcDailyReturnRate(cur, prev)` | 现价、前日收盘 | 个股当日涨跌幅 | 后端 `daily_return_rate` |
| `calcCumReturn(nav, cost)` | 总市值、总成本 | 组合累计收益 | 后端 `latest_cumulative_return` |
| `calcDailyReturns(navSeries)` | NAV 序列 `[{date,nav}]` | `Map<日期, {return_amount, return_rate}>` | `/daily-returns` 端点 |
| `calcMonthlyReturns(navSeries, year)` | NAV 序列 + 年份 | `[{month, return_amount, return_rate}]` | `/monthly-returns` 端点 |
| `fmtMoney(v)` | 数值 | 格式化金额字符串 | — |
| `fmtRate(v)` | 数值 | 格式化百分比字符串 | — |
| `moneyClass(v)` / `rateClass(v)` | 数值 | CSS 类名 (up/down/zero) | — |

### 后端为此新增的原始数据字段

| Schema | 字段 | 用途 |
|--------|------|------|
| `HoldingResponse` | `prev_close` | 前一交易日收盘价，供前端算当日收益率 |
| `PortfolioDetail` | `latest_total_cost` | 最新总成本，供前端算累计收益 |
| `PortfolioSummary` | `latest_total_cost` | 同上（列表页） |

### 后端标注

后端中标记为「便捷计算（前端也可完成）」的计算，接口保持不变但注释说明了前端替代方式，
后续如需进一步精简后端可直接移除这些计算而前端不受影响。
