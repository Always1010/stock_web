# 股票模拟交易 Web 应用

A股股票模拟交易系统。支持自选股管理、K线图表、多组合管理、净值追踪与收益分析。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Element Plus + ECharts 5 |
| 后端 | FastAPI + SQLAlchemy 2.0 + APScheduler |
| 数据库 | MySQL 8.0 |
| 数据源 | Sina Finance API |
| 部署 | Nginx + uvicorn/gunicorn |

---

## 数据库说明

### SQL 文件在哪里？

表结构有两种来源，**二选一即可**：

| 方式 | 文件 | 说明 |
|------|------|------|
| **Alembic 迁移（推荐）** | `backend/alembic/versions/` | 版本化管理，`install.sh` 自动执行 |
| **参考 SQL** | `backend/schema.sql` | 纯 SQL，可手动 `mysql < schema.sql` 导入 |

**`install.sh` 使用的是 Alembic 方式**：在第 3 步安装完 Python 依赖后，自动执行 `alembic upgrade head`，将表结构创建到 MySQL。

### install.sh 什么时候创建数据库？

```
[2/5] Setting up MySQL database...
  → 创建数据库 stock_web（如果不存在）
  → 创建用户 stock@localhost，密码 stock123
  → 授权

[3/5] Installing Python backend dependencies...
  → pip install -r requirements.txt
  → alembic upgrade head    ← 表结构在这里创建
```

**注意**：`install.sh` 只负责 **安装依赖 + 创建空表**。它**不会启动后端进程**，也不会导入示例数据。

---

## 快速启动

项目必须**手动启动**。`install.sh` 只执行一次（装环境），之后用 `start.sh`。

### 第一次：安装环境

```bash
cd /home/ubuntu/wrk/stock_web
bash install.sh
```

`install.sh` 做了这些事：
1. 安装 MySQL 8.0、Node.js 22、Python venv
2. 创建 `stock_web` 数据库和 `stock` 用户
3. 安装 Python 依赖到 `backend/venv/`
4. 执行 Alembic 迁移创建表结构
5. 安装前端 npm 依赖并构建

### 之后每次启动

```bash
# 启动（生产模式：gunicorn + nginx，访问 :80）
bash start.sh

# 或开发模式（uvicorn + vite，访问 :5173）
bash start.sh dev

# 停止
bash stop.sh
```

### 手动启动后端

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# API 文档: http://localhost:8000/api/docs
```

### 手动启动前端

```bash
cd frontend
npm run dev
# 页面: http://localhost:5173（自动代理 /api → :8000）
```

---

## 导入示例数据

`install.sh` 创建的是**空表**。如需演示数据：

```bash
cd backend
source venv/bin/activate

# 方法1：手动爬取真实数据
python cli.py crawl-stock-list      # 爬取A股列表（约5000只）
python cli.py crawl-kline --code 600519  # 爬取单只股票K线

# 方法2：生成示例数据（当前已生成15只股票+4155条K线）
python3 -c "
from app.database import SessionLocal
from app.models.stock import Stock
db = SessionLocal()
print(f'Stocks: {db.query(Stock).count()}')
"
```

---

## 常用操作

### 爬取数据

```bash
cd backend && source venv/bin/activate

python cli.py crawl-stock-list          # 爬取A股列表
python cli.py crawl-kline --all         # 爬取全部K线（耗时长）
python cli.py crawl-kline --code 600519 # 爬取单只股票

python cli.py update-nav                # 手动更新所有组合净值
```

### 生产部署（systemd 开机自启）

```bash
# 安装 systemd 服务
sudo cp stock-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stock-web
sudo systemctl start stock-web

# 查看状态
sudo systemctl status stock-web
```

### 数据库维护

```bash
# 查看 Alembic 迁移状态
cd backend && source venv/bin/activate
alembic current
alembic history

# 手动创建新迁移（修改 Model 后）
alembic revision --autogenerate -m "描述"
alembic upgrade head

# 回滚一个版本
alembic downgrade -1
```

---

## 项目结构

```
stock_web/
├── start.sh               # 启动脚本
├── stop.sh                # 停止脚本
├── install.sh             # 一键安装（仅首次执行）
├── stock-web.service      # systemd 服务文件
├── ARCHITECTURE.md        # 架构设计文档
│
├── frontend/              # Vue 3 前端
│   ├── src/
│   │   ├── views/         # 页面: Login, Dashboard, StockSearch,
│   │   │                  #   KlineChart, Watchlist, PortfolioList,
│   │   │                  #   PortfolioCreate, PortfolioDetail
│   │   ├── components/    # AppLayout
│   │   ├── router/        # Vue Router 路由配置
│   │   ├── stores/        # Pinia 状态 (auth)
│   │   ├── api/           # Axios 封装 + 拦截器
│   │   └── utils/         # 格式化工具
│   └── dist/              # 构建产物（Nginx 托管）
│
├── backend/               # FastAPI 后端
│   ├── app/
│   │   ├── main.py        # FastAPI 入口
│   │   ├── config.py      # 配置（DB URL, JWT, 调度时间）
│   │   ├── database.py    # SQLAlchemy Engine + Session
│   │   ├── models/        # 7 个 SQLAlchemy 模型
│   │   ├── schemas/       # Pydantic 请求/响应模型
│   │   ├── routers/       # API 路由（auth/stocks/watchlist/portfolio）
│   │   ├── services/      # 业务逻辑（爬虫/净值计算/调度）
│   │   └── utils/         # JWT + 密码 + 日期工具
│   ├── alembic/           # 数据库迁移
│   │   └── versions/      # 迁移文件（版本化SQL）
│   ├── schema.sql         # 参考 SQL（非执行文件）
│   ├── cli.py             # 命令行工具
│   └── requirements.txt
│
└── nginx/
    └── stock-web.conf     # Nginx 站点配置
```

---

## 定时任务

| 时间 | 任务 | 说明 |
|------|------|------|
| 每天 06:00 | 爬取股票列表 + K线 | APScheduler，在进程中运行 |
| 每天 15:05 | 更新所有组合净值 | 收盘后 5 分钟执行 |

任务在 `backend/app/services/scheduler.py` 定义，FastAPI 启动时自动注册。

---

## 成本价逻辑

| 场景 | 行为 |
|------|------|
| 用户手动填写成本价 | 直接使用，立即锁定 |
| 不填写，当前时间 < 15:00 | 自动取上一交易日收盘价 |
| 不填写，当前时间 >= 15:00 | 自动取当日收盘价（无则取最近交易日） |
| 成本价已设定后再次修改 | **拒绝**，成本价不可变 |

---

## 当前运行状态

```bash
# 查看进程
ps aux | grep -E "uvicorn|gunicorn|vite" | grep -v grep

# 查看数据库
mysql -u stock -pstock123 stock_web -e "SHOW TABLES;"
mysql -u stock -pstock123 stock_web -e "SELECT count(*) stocks FROM stocks;"
```

- 后端日志: `/tmp/stock-web-backend.log` 或 `journalctl -u stock-web`
- Nginx 日志: `/var/log/nginx/access.log`  `/var/log/nginx/error.log`
