-- ============================================================
-- Stock Simulation Web App - Database Schema
-- Database: stock_web (MySQL 8.0, utf8mb4)
--
-- This file is for REFERENCE. Production schema is managed by
-- Alembic migrations in backend/alembic/versions/
-- ============================================================

CREATE DATABASE IF NOT EXISTS stock_web
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE stock_web;

-- ── Users ───────────────────────────────────────────────────
CREATE TABLE users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT (NOW())
) ENGINE=InnoDB;

-- ── A-share Stock Master ────────────────────────────────────
-- exchange: SH = 上海, SZ = 深圳, BJ = 北京
CREATE TABLE stocks (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(6)   NOT NULL UNIQUE,
    exchange        ENUM('SH','SZ','BJ') NOT NULL,
    name            VARCHAR(64)  NOT NULL,
    is_active       INT          NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    updated_at      DATETIME     NOT NULL DEFAULT (NOW()),
    UNIQUE KEY uk_code (code)
) ENGINE=InnoDB;

-- ── Daily K-line (Candlestick) ──────────────────────────────
-- One record per stock per trading day
-- UNIQUE(stock_id, trade_date) enforced by application + DB
CREATE TABLE daily_kline (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    stock_id        INT          NOT NULL,
    trade_date      DATE         NOT NULL,
    open            FLOAT        NOT NULL,
    high            FLOAT        NOT NULL,
    low             FLOAT        NOT NULL,
    close           FLOAT        NOT NULL,
    volume          BIGINT       NOT NULL,
    amount          FLOAT        NOT NULL,
    UNIQUE KEY uk_stock_date (stock_id, trade_date),
    INDEX idx_stock_date (stock_id, trade_date),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
) ENGINE=InnoDB;

-- ── User Watchlist ──────────────────────────────────────────
-- One entry per user-stock pair
CREATE TABLE watchlist_items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    stock_id        INT          NOT NULL,
    added_at        DATETIME     NOT NULL DEFAULT (NOW()),
    UNIQUE KEY uk_user_stock (user_id, stock_id),
    INDEX idx_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
) ENGINE=InnoDB;

-- ── Portfolio ───────────────────────────────────────────────
-- code: auto-generated, e.g. PF20260624001
CREATE TABLE portfolios (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT          NOT NULL,
    name            VARCHAR(128) NOT NULL,
    code            VARCHAR(20)  NOT NULL UNIQUE,
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    updated_at      DATETIME     NOT NULL DEFAULT (NOW()),
    INDEX idx_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- ── Portfolio Holdings ──────────────────────────────────────
-- cost_price: NULL until explicitly set, IMMUTABLE once set
CREATE TABLE portfolio_holdings (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id      INT        NOT NULL,
    stock_id          INT        NOT NULL,
    shares            FLOAT      NOT NULL,
    cost_price        FLOAT      DEFAULT NULL,
    cost_price_set_at DATETIME   DEFAULT NULL,
    created_at        DATETIME   NOT NULL DEFAULT (NOW()),
    UNIQUE KEY uk_portfolio_stock (portfolio_id, stock_id),
    INDEX idx_portfolio (portfolio_id),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    FOREIGN KEY (stock_id)     REFERENCES stocks(id)
) ENGINE=InnoDB;

-- ── Portfolio NAV History (daily snapshot) ──────────────────
-- One record per portfolio per trading day
CREATE TABLE portfolio_nav_history (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    portfolio_id        INT        NOT NULL,
    nav_date            DATE       NOT NULL,
    nav                 FLOAT      NOT NULL,
    daily_return        FLOAT      DEFAULT NULL,
    daily_return_rate   FLOAT      DEFAULT NULL,
    cum_return_rate     FLOAT      DEFAULT NULL,
    total_cost          FLOAT      NOT NULL DEFAULT 0,
    total_market_value  FLOAT      NOT NULL DEFAULT 0,
    created_at          DATETIME   NOT NULL DEFAULT (NOW()),
    UNIQUE KEY uk_portfolio_date (portfolio_id, nav_date),
    INDEX idx_portfolio_date (portfolio_id, nav_date),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ── Crawl Log (observability) ───────────────────────────────
CREATE TABLE crawl_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    crawl_type      VARCHAR(32)  NOT NULL,
    ref_date        DATE         NOT NULL,
    status          VARCHAR(16)  NOT NULL,
    details         JSON         DEFAULT NULL,
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    INDEX idx_type_date (crawl_type, ref_date)
) ENGINE=InnoDB;

-- ============================================================
-- End of schema
-- ============================================================
