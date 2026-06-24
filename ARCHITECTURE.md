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
│   │   └── utils/               # Formatters
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
├── install.sh
└── README.md
```

## Database Schema

```
users (1) ────── (N) watchlist_items (N) ────── (1) stocks (1) ────── (N) daily_kline
users (1) ────── (N) portfolios (1) ────── (N) portfolio_holdings (N) ────── (1) stocks
portfolios (1) ────── (N) portfolio_nav_history
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

## API Design

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /api/auth/register | No | Register |
| POST | /api/auth/login | No | Login → JWT |
| GET | /api/auth/me | Yes | Current user |
| GET | /api/stocks | Yes | Search stocks |
| GET | /api/stocks/{code} | Yes | Stock detail |
| GET | /api/stocks/{code}/kline | Yes | K-line data |
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
