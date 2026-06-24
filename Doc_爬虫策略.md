# 爬虫策略文档

## 数据源

| 数据类型 | 数据源 | API | 格式 |
|----------|--------|-----|------|
| 股票列表 | 新浪财经 | `Market_Center.getHQNodeData`（node=hs_a） | JSON 数组 |
| 个股日K线 | 新浪财经 | `CN_MarketData.getKLineData`（scale=240） | JSON 数组 |
| 指数实时行情 | 新浪财经 | `hq.sinajs.cn/list=` | GBK 编码文本 |
| 指数日K线 | 新浪财经 | `CN_MarketData.getKLineData`（scale=240） | JSON 数组 |
| 行业板块 | 东方财富 | `push2.eastmoney.com/api/qt/clist/get`（fs=m:90+t:2） | JSON |

---

## 爬取数据总览

共 9 个爬虫函数，覆盖 8 张数据表：

```
crawl_stock_list()        →  stocks
crawl_kline_for_stock()   →  daily_kline
crawl_kline_on_demand()   →  daily_kline（按需触发）
crawl_all_kline()         →  daily_kline（全量遍历）
crawl_market_indices()    →  market_index
crawl_market_breadth()    →  market_breadth
crawl_sectors()           →  sector_data
crawl_index_kline()       →  index_kline
crawl_market_turnover()   →  market_turnover
```

---

## 一、股票列表爬取

### `crawl_stock_list()`

**触发方式**：定时（每天 06:00）+ CLI 手动

**数据流**：
```
新浪 hs_a → 分页遍历（每页100条，间隔0.3s）
         → 解析 code/name
         → _determine_exchange() 判定交易所
         → UPSERT 写入 stocks 表
         → 记录 CrawlLog
```

**交易所判定**（`_determine_exchange`）：

| 前缀 | 交易所 | 说明 |
|------|--------|------|
| `6` | SH（上海） | 60xxxx 主板、68xxxx 科创板 |
| `0`, `3` | SZ（深圳） | 00xxxx 主板、30xxxx 创业板 |
| `8`, `4`, `92` | BJ（北交所） | 92xxxx 为北交所新代码体系 |

**产出**：约 5500 只 A 股（包含沪深京三地）

**重复处理**：`code` 已存在 → 仅更新名称；不存在 → 新增

---

## 二、个股日K线

### `crawl_kline_for_stock(stock, db, datalen=400)`

**触发方式**：定时全量 + 按需触发

**数据流**：
```
symbol = sh600519 / sz000001 / bj920000（_sina_symbol 转换）
       → 新浪 K 线 API（datalen=400，约2年日线）
       → 解析 day/open/high/low/close/volume/amount
       → INSERT IGNORE 写入 daily_kline（stock_id + trade_date 唯一）
```

**`crawl_all_kline(limit=None)`**：遍历所有 active 股票，间隔 0.5s（~2 req/s）。5500 只股票全量约需 45 分钟。

**`crawl_kline_on_demand(stock, db)`**：前端查看 K 线时，若无缓存数据则自动触发。返回缓存后的全量数据。

---

## 三、市场指数实时行情

### `crawl_market_indices()`

**触发方式**：定时（每天 15:05，收盘后 5 分钟）

**覆盖指数**（`INDEX_CONFIG`）：

| 代码 | 名称 | 交易所 |
|------|------|--------|
| sh000001 | 上证指数 | 上海 |
| sz399001 | 深证成指 | 深圳 |
| sz399006 | 创业板指 | 深圳 |
| sh000688 | 科创50 | 上海 |
| sh000300 | 沪深300 | 上海 |

**数据流**：
```
hq.sinajs.cn/list=sh000001,...,sh000300
  → GBK 文本解析（正则 var hq_str_xxx="..."）
  → 提取 name/open/prev_close/current/high/low
  → 计算 change/change_pct
  → UPSERT 写入 market_index（code + trade_date 唯一）
```

**API 示例**：
```
var hq_str_sh000001="上证指数,4110.81,4106.25,4114.56,4117.45,4080.29,..."
                   name    open    prev_close current high   low
```

---

## 四、指数日K线

### `crawl_index_kline(code, name, db, datalen=400)`

**触发方式**：定时（15:05）+ 前端查看时按需触发

**数据流**：复用个股 K 线 API，symbol 直接为 `sh000001` 等格式。存入 `index_kline` 表。

---

## 五、市场涨跌统计

### `crawl_market_breadth()`

**触发方式**：定时（每天 15:05）

**计算逻辑**：
```
取 daily_kline 最新 trade_date
  → 按交易所分组（SH / SZ / BJ）
  → 遍历每只股票的当日 K 线
  → close > open → 涨 | close < open → 跌 | == → 平
  → 汇总写入 market_breadth
```

**注意**：涨跌统计的准确性取决于 K 线数据的覆盖量。只有被爬取了 K 线的股票才会纳入统计。

---

## 六、行业板块

### `crawl_sectors()`

**触发方式**：定时（每天 15:05）

**数据流**：
```
东方财富板块 API（fs=m:90+t:2，fid=f3 按涨跌幅排序）
  → 取前 30 个板块
  → 提取 code/name/涨跌幅/领涨股/领涨股涨幅/排名
  → UPSERT 写入 sector_data
```

---

## 七、市场总成交额

### `crawl_market_turnover()`

**触发方式**：定时（15:05）+ 前端查看时按需触发

**计算逻辑**：
```
取 daily_kline 最新 trade_date
  → SUM(amount) 合计成交额
  → SUM(volume) 合计成交量
  → COUNT(*) 有数据的股票数
  → UPSERT 写入 market_turnover
```

**注意**：成交额为全市场汇总，依赖于 K 线数据覆盖量。

---

## 八、调度策略

APScheduler 在 FastAPI 启动时自动注册 2 个定时任务（均在 CST 时区）：

| 时间 | Job | 执行内容 |
|------|-----|----------|
| 每天 **06:00** | `_crawl_job` | ① `crawl_stock_list()` — 全量刷新股票列表<br>② `crawl_all_kline()` — 全量更新所有股票日K线 |
| 每天 **15:05** | `_nav_update_job` | ① `update_all_portfolios_nav()` — 更新组合净值<br>② `crawl_all_market_data()` — 爬取全部市场数据：<br>　├ 指数实时行情<br>　├ 市场涨跌统计<br>　├ 行业板块排名<br>　├ 指数日K线<br>　└ 市场总成交额 |

**设计理由**：
- **06:00**：盘前，K 线数据已确认（前一日收盘），有充足的 3.5 小时窗口完成全量抓取
- **15:05**：收盘后 5 分钟，保证当日行情数据已生成，同时更新组合净值和市场统计

---

## 九、容错与重试

| 机制 | 说明 |
|------|------|
| HTTP 重试 | `_http_get_json()` 含 3 次重试，指数退避（1s / 2s / 4s） |
| 逐条容错 | `crawl_all_kline()` 中单只股票失败不影响后续 |
| 市场数据独立 | `crawl_all_market_data()` 中指数/涨跌/板块各自 try/except，互不阻塞 |
| 日志记录 | 每次爬取结果写入 `crawl_log` 表（状态 + 明细 JSON） |
| 按需补抓 | K 线、指数 K 线、成交额支持前端查看时自动补抓（on-demand） |

---

## 十、CLI 手动操作

```bash
cd backend && source ../venv/bin/activate

# 爬取股票列表（全量）
python cli.py crawl-stock-list

# 爬取单只股票 K 线
python cli.py crawl-kline --code 600519

# 爬取全部股票 K 线（耗时较长）
python cli.py crawl-kline --all

# 手动更新净值 + 市场数据
python cli.py update-nav

# 单独跑市场数据爬取
python -c "from app.services.crawler import crawl_all_market_data; print(crawl_all_market_data())"

# 单独跑成交额
python -c "from app.services.crawler import crawl_market_turnover; print(crawl_market_turnover())"
```
