# CLAUDE.md — Stock Simulation Web

## 项目概述

A 股模拟交易 Web 应用。前后端分离：Vue 3 + FastAPI + MySQL 8.0。

## 工作流程规范

### 修改前必须出计划

任何非 trivial 的修改，先写出简短计划（要改哪些文件、分几步），再逐步实施。这样方便追溯和回滚。

### 每完成一个小点就 commit

不要把多个独立改动揉成一个 commit。commit 类型遵循以下规范：

| Type | 含义 | 示例 |
|------|------|------|
| **NEW** | 新增功能/特性 | `NEW: 新增市场行情概览页面` |
| **FIX** | 修复 bug | `FIX: 修复 JWT sub 字段类型错误` |
| **DOCS** | 仅文档变更 | `DOCS: 更新 API 路由说明` |
| **STYLE** | 代码格式（空格/缩进/逗号等），不改变逻辑 | `STYLE: 统一缩进为 4 空格` |
| **REFC** | 代码重构，无新功能无 bug 修复 | `REFC: 抽取公共请求工具函数` |
| **ENH** | 优化（性能/体验提升） | `ENH: K 线图添加数据缩放组件` |
| **TEST** | 测试用例（单元/集成） | `TEST: 添加净值计算单元测试` |
| **CHORE** | 构建/依赖/工具变更 | `CHORE: 升级 Vite 到 v8` |
| **REVERT** | 回滚 | `REVERT: 回滚到 b429d5c` |

**提交信息要求**：
- 用中文，30 字以内
- 描述准确简洁，方便 `git log --oneline` 快速浏览
- 一个 commit 只做一件事
- 不需要正文，除非有特别需要说明的背景

### 会话结束前记录日志

每次会话结束时，用 `python3 ~/.claude/scripts/log.py` 记录到项目根目录的 `session-log.md`。

## 常用命令

```bash
# 后端
cd backend && source ../venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# API 文档: http://localhost:8000/api/docs

# 前端
cd frontend && npm run dev     # 开发 :5173
cd frontend && npm run build   # 构建

# 数据库迁移
cd backend && source ../venv/bin/activate
alembic revision --autogenerate -m "描述"
alembic upgrade head

# CLI 工具
python cli.py crawl-stock-list
python cli.py crawl-kline --all
python cli.py update-nav

# 生产部署
sudo systemctl reload nginx
# 后端日志: /tmp/uvicorn.log
```

## 关键文件索引

- `Doc_架构说明.md` — 架构文档（技术栈、数据库、API 表）
- `Doc_commit规范.md` — Commit 规范详细说明
- `Doc_需求说明.md` — 需求文档
- `Doc_爬虫策略.md` — 爬虫数据源、函数、调度、容错说明
- `backend/app/models/` — 10 个 SQLAlchemy 模型
- `backend/app/routers/` — 5 组 API 路由
- `backend/app/services/` — 爬虫、净值计算、调度器
- `frontend/src/views/` — 9 个页面组件
- `frontend/src/styles/` — 设计系统（variables.css + global.css）
