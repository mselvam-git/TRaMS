-- TRaMS Portfolio — Database Schema Extension
-- Run: psql -U selvam -d central_portfolio -f db_migrate.sql

-- ── Extend brokers with owner & TRaMS metadata ───────────────────
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS owner       VARCHAR DEFAULT 'selvam';
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS native_ccy  VARCHAR DEFAULT 'INR';
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS connected   BOOLEAN DEFAULT TRUE;

-- Upsert all 5 brokers
INSERT INTO brokers (name, country, base_currency, owner, native_ccy, connected) VALUES
  ('Zerodha',             'India', 'INR', 'selvam',  'INR', TRUE),
  ('Sharekhan',           'India', 'INR', 'selvam',  'INR', TRUE),
  ('Interactive Brokers', 'USA',   'EUR', 'both',    'EUR', TRUE),
  ('eToro',               'CY',    'USD', 'both',    'USD', TRUE),
  ('Aionion Capital',     'India', 'INR', 'radhika', 'INR', TRUE)
ON CONFLICT (name) DO UPDATE SET
  owner      = EXCLUDED.owner,
  native_ccy = EXCLUDED.native_ccy,
  connected  = EXCLUDED.connected;

ALTER TABLE brokers ADD CONSTRAINT brokers_name_unique UNIQUE (name);

-- ── Extend accounts with owner ───────────────────────────────────
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS owner       VARCHAR DEFAULT 'selvam';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_label VARCHAR;

UPDATE accounts SET owner = 'selvam'  WHERE account_number = 'U15214441';
UPDATE accounts SET owner = 'radhika' WHERE account_number = 'U20199465';
UPDATE accounts SET owner = 'selvam'  WHERE account_number = 'ZERODHA_MAIN';

-- ── Daily Portfolio Snapshots ────────────────────────────────────
-- Stores total portfolio value per day per owner — powers the growth chart
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id            SERIAL PRIMARY KEY,
  snapshot_date DATE        NOT NULL DEFAULT CURRENT_DATE,
  owner         VARCHAR(20) NOT NULL,               -- 'selvam', 'radhika', 'combined'
  broker        VARCHAR(50),                         -- NULL = combined total
  total_value   DOUBLE PRECISION NOT NULL,
  total_invested DOUBLE PRECISION,
  total_pnl     DOUBLE PRECISION,
  currency      VARCHAR(10) DEFAULT 'INR',
  fx_usd_inr    DOUBLE PRECISION DEFAULT 83.5,
  fx_eur_inr    DOUBLE PRECISION DEFAULT 90.2,
  created_at    TIMESTAMP   DEFAULT NOW(),
  UNIQUE (snapshot_date, owner, broker)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date  ON portfolio_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_owner ON portfolio_snapshots(owner);

-- ── Holdings History ─────────────────────────────────────────────
-- Daily snapshot of every holding — lets you track individual stock growth
CREATE TABLE IF NOT EXISTS holdings_history (
  id            SERIAL PRIMARY KEY,
  snapshot_date DATE        NOT NULL DEFAULT CURRENT_DATE,
  owner         VARCHAR(20) NOT NULL,
  broker        VARCHAR(50) NOT NULL,
  symbol        VARCHAR(30) NOT NULL,
  name          VARCHAR(200),
  asset_type    VARCHAR(20),
  quantity      DOUBLE PRECISION,
  avg_price     DOUBLE PRECISION,
  current_price DOUBLE PRECISION,
  current_value DOUBLE PRECISION,
  invested_value DOUBLE PRECISION,
  pnl           DOUBLE PRECISION,
  pnl_percent   DOUBLE PRECISION,
  currency      VARCHAR(10) DEFAULT 'INR',
  created_at    TIMESTAMP   DEFAULT NOW(),
  UNIQUE (snapshot_date, owner, broker, symbol)
);

CREATE INDEX IF NOT EXISTS idx_holdings_hist_date   ON holdings_history(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_holdings_hist_symbol ON holdings_history(symbol);
CREATE INDEX IF NOT EXISTS idx_holdings_hist_owner  ON holdings_history(owner);

-- ── Bonds History ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bonds_history (
  id              SERIAL PRIMARY KEY,
  snapshot_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
  owner           VARCHAR(20) DEFAULT 'radhika',
  isin            VARCHAR(30),
  symbol          VARCHAR(50),
  name            VARCHAR(200),
  principal_amount DOUBLE PRECISION,
  coupon_rate     DOUBLE PRECISION,
  ytm             DOUBLE PRECISION,
  ytc             DOUBLE PRECISION,
  maturity_date   VARCHAR(50),
  call_date       VARCHAR(50),
  currency        VARCHAR(10) DEFAULT 'INR',
  created_at      TIMESTAMP   DEFAULT NOW(),
  UNIQUE (snapshot_date, isin)
);

-- ── FX Rates History ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fx_rates (
  id          SERIAL PRIMARY KEY,
  rate_date   DATE    NOT NULL DEFAULT CURRENT_DATE,
  usd_inr     DOUBLE PRECISION,
  eur_inr     DOUBLE PRECISION,
  created_at  TIMESTAMP DEFAULT NOW(),
  UNIQUE (rate_date)
);

-- Insert today's rates as baseline
INSERT INTO fx_rates (rate_date, usd_inr, eur_inr) 
VALUES (CURRENT_DATE, 83.5, 90.2)
ON CONFLICT (rate_date) DO NOTHING;

SELECT 'TRaMS schema migration complete ✓' AS status;
