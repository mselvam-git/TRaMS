-- ═══════════════════════════════════════════════════════════════
-- TRaMS Portfolio Database
-- Database: trams_portfolio
-- Run: psql -U selvam -d postgres -f trams_db_init.sql
-- ═══════════════════════════════════════════════════════════════

-- Create database
CREATE DATABASE trams_portfolio
  OWNER selvam
  ENCODING 'UTF8'
  LC_COLLATE 'en_US.UTF-8'
  LC_CTYPE 'en_US.UTF-8';

\c trams_portfolio

-- ── FX Rates ─────────────────────────────────────────────────────
CREATE TABLE fx_rates (
  id         SERIAL PRIMARY KEY,
  rate_date  DATE        NOT NULL DEFAULT CURRENT_DATE,
  usd_inr    DOUBLE PRECISION NOT NULL DEFAULT 83.5,
  eur_inr    DOUBLE PRECISION NOT NULL DEFAULT 90.2,
  updated_at TIMESTAMP   DEFAULT NOW(),
  UNIQUE (rate_date)
);
CREATE INDEX ON fx_rates(rate_date DESC);
INSERT INTO fx_rates (rate_date, usd_inr, eur_inr) VALUES (CURRENT_DATE, 83.5, 90.2);

-- ── Instruments (shared cache — avoids repeat API calls) ──────────
-- Stores instrument/symbol details fetched once from eToro, yfinance, etc.
CREATE TABLE instruments (
  id              SERIAL PRIMARY KEY,
  instrument_id   INTEGER,              -- eToro internal ID (null for non-eToro)
  symbol          VARCHAR(30) NOT NULL,
  name            VARCHAR(200),
  full_name       VARCHAR(300),
  asset_type      VARCHAR(20) DEFAULT 'stock',
  asset_class_id  INTEGER,              -- eToro assetClassId
  currency        VARCHAR(10) DEFAULT 'USD',
  exchange        VARCHAR(30),
  source          VARCHAR(20) DEFAULT 'etoro',  -- 'etoro','nse','bse','ibkr'
  fetched_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE (source, symbol),
  UNIQUE (instrument_id)               -- null-safe: allows multiple nulls
);
CREATE INDEX ON instruments(symbol);
CREATE INDEX ON instruments(instrument_id);

-- ── Owners ───────────────────────────────────────────────────────
CREATE TABLE owners (
  id    SERIAL PRIMARY KEY,
  name  VARCHAR(20) NOT NULL UNIQUE,   -- 'selvam', 'radhika'
  label VARCHAR(50)
);
INSERT INTO owners (name, label) VALUES
  ('selvam',  'Selvam'),
  ('radhika', 'Radhika');

-- ── Brokers ──────────────────────────────────────────────────────
CREATE TABLE brokers (
  id           SERIAL PRIMARY KEY,
  name         VARCHAR(50) NOT NULL UNIQUE,
  owner        VARCHAR(20) NOT NULL,   -- 'selvam','radhika','both'
  native_ccy   VARCHAR(10) DEFAULT 'INR',
  connected    BOOLEAN DEFAULT TRUE,
  auth_method  VARCHAR(20),            -- 'api_key','oauth','csv','ib_gateway'
  notes        TEXT
);
INSERT INTO brokers (name, owner, native_ccy, auth_method) VALUES
  ('Zerodha',             'selvam',  'INR', 'oauth'),
  ('Sharekhan',           'selvam',  'INR', 'oauth'),
  ('Interactive Brokers', 'both',    'EUR', 'ib_gateway'),
  ('eToro',               'both',    'USD', 'api_key'),
  ('Aionion Capital',     'radhika', 'INR', 'jwt');

-- ── eToro Copy Traders (mirrors) ─────────────────────────────────
-- One row per copy relationship (person → copied trader)
CREATE TABLE etoro_copy_traders (
  id                  SERIAL PRIMARY KEY,
  owner               VARCHAR(20) NOT NULL,  -- 'selvam' or 'radhika'
  mirror_id           BIGINT NOT NULL UNIQUE,
  trader_username     VARCHAR(100),
  trader_cid          BIGINT,
  initial_investment  DOUBLE PRECISION DEFAULT 0,
  deposit_summary     DOUBLE PRECISION DEFAULT 0,
  withdrawal_summary  DOUBLE PRECISION DEFAULT 0,
  available_amount    DOUBLE PRECISION DEFAULT 0,
  is_paused           BOOLEAN DEFAULT FALSE,
  started_copy_date   TIMESTAMP,
  last_seen           DATE DEFAULT CURRENT_DATE,
  UNIQUE (owner, mirror_id)
);
CREATE INDEX ON etoro_copy_traders(owner);

-- ── Portfolio Snapshots ───────────────────────────────────────────
-- Daily value per owner / broker / copy_trader
CREATE TABLE portfolio_snapshots (
  id              SERIAL PRIMARY KEY,
  snapshot_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
  owner           VARCHAR(20) NOT NULL,
  broker          VARCHAR(50),             -- NULL = all-broker total
  sub_account     VARCHAR(100),            -- copy trader username (eToro mirrors)
  total_value_inr DOUBLE PRECISION NOT NULL,
  total_invested_inr DOUBLE PRECISION DEFAULT 0,
  total_pnl_inr   DOUBLE PRECISION DEFAULT 0,
  fx_usd_inr      DOUBLE PRECISION DEFAULT 83.5,
  fx_eur_inr      DOUBLE PRECISION DEFAULT 90.2,
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE (snapshot_date, owner, broker, sub_account)
);
CREATE INDEX ON portfolio_snapshots(snapshot_date DESC);
CREATE INDEX ON portfolio_snapshots(owner);
CREATE INDEX ON portfolio_snapshots(broker);

-- ── Holdings History ──────────────────────────────────────────────
CREATE TABLE holdings_history (
  id              SERIAL PRIMARY KEY,
  snapshot_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
  owner           VARCHAR(20) NOT NULL,
  broker          VARCHAR(50) NOT NULL,
  sub_account     VARCHAR(100),           -- copy trader username for eToro mirrors
  symbol          VARCHAR(30) NOT NULL,
  instrument_id   INTEGER REFERENCES instruments(id) ON DELETE SET NULL,
  asset_type      VARCHAR(20),
  quantity        DOUBLE PRECISION,
  avg_price       DOUBLE PRECISION,
  current_price   DOUBLE PRECISION,
  current_value   DOUBLE PRECISION,
  invested_value  DOUBLE PRECISION,
  pnl             DOUBLE PRECISION,
  pnl_percent     DOUBLE PRECISION,
  currency        VARCHAR(10) DEFAULT 'INR',
  created_at      TIMESTAMP DEFAULT NOW(),
  UNIQUE (snapshot_date, owner, broker, sub_account, symbol)
);
CREATE INDEX ON holdings_history(snapshot_date DESC);
CREATE INDEX ON holdings_history(symbol);
CREATE INDEX ON holdings_history(owner);
CREATE INDEX ON holdings_history(broker, sub_account);

-- ── Bonds History ────────────────────────────────────────────────
CREATE TABLE bonds_history (
  id               SERIAL PRIMARY KEY,
  snapshot_date    DATE NOT NULL DEFAULT CURRENT_DATE,
  owner            VARCHAR(20) DEFAULT 'radhika',
  isin             VARCHAR(30),
  symbol           VARCHAR(50),
  name             VARCHAR(300),
  principal_amount DOUBLE PRECISION,
  coupon_rate      DOUBLE PRECISION,
  ytm              DOUBLE PRECISION,
  ytc              DOUBLE PRECISION,
  maturity_date    VARCHAR(50),
  call_date        VARCHAR(50),
  currency         VARCHAR(10) DEFAULT 'INR',
  created_at       TIMESTAMP DEFAULT NOW(),
  UNIQUE (snapshot_date, isin)
);
CREATE INDEX ON bonds_history(snapshot_date DESC);

-- ── Views ────────────────────────────────────────────────────────
-- Latest portfolio value per owner
CREATE VIEW v_latest_portfolio AS
SELECT owner, SUM(total_value_inr) AS total_inr
FROM portfolio_snapshots
WHERE broker IS NULL
  AND sub_account IS NULL
  AND snapshot_date = (SELECT MAX(snapshot_date) FROM portfolio_snapshots WHERE broker IS NULL)
GROUP BY owner;

-- Copy trader performance summary
CREATE VIEW v_copy_trader_summary AS
SELECT
  ps.owner,
  ps.sub_account AS trader,
  ps.snapshot_date,
  ps.total_value_inr,
  ps.total_invested_inr,
  ps.total_pnl_inr,
  CASE WHEN ps.total_invested_inr > 0
    THEN ROUND((ps.total_pnl_inr / ps.total_invested_inr * 100)::numeric, 2)
    ELSE 0 END AS pnl_pct
FROM portfolio_snapshots ps
WHERE ps.broker = 'eToro' AND ps.sub_account IS NOT NULL;

SELECT 'TRaMS DB initialized ✓' AS status;
