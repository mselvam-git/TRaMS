"""
TRaMS Database Service — trams_portfolio
==========================================
PostgreSQL connection, instrument cache, snapshots, history queries.
"""
import os
from datetime import date
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

def _conn():
    load_dotenv(ENV_PATH, override=True)
    import psycopg2
    # Prefer DATABASE_URL (Neon / Render / Heroku style) over individual params
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        return psycopg2.connect(db_url)
    return psycopg2.connect(
        host     = os.getenv("DB_HOST", "localhost"),
        port     = int(os.getenv("DB_PORT", 5432)),
        dbname   = os.getenv("DB_NAME", "trams_portfolio"),
        user     = os.getenv("DB_USER", "selvam"),
        password = os.getenv("DB_PASSWORD", "") or None,
    )

def db_health() -> bool:
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except:
        return False

# ── FX Rates ─────────────────────────────────────────────────────

def update_fx_rates(usd_inr: float, eur_inr: float):
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    INSERT INTO fx_rates (rate_date, usd_inr, eur_inr)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (rate_date) DO UPDATE SET
                      usd_inr=EXCLUDED.usd_inr, eur_inr=EXCLUDED.eur_inr, updated_at=NOW()
                """, (date.today(), usd_inr, eur_inr))
    except Exception as e:
        print(f"[DB] update_fx_rates: {e}")

def get_latest_fx() -> Dict:
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("SELECT usd_inr, eur_inr FROM fx_rates ORDER BY rate_date DESC LIMIT 1")
                r = cur.fetchone()
                if r:
                    return {"USD": float(r[0]), "EUR": float(r[1])}
    except Exception as e:
        print(f"[DB] get_latest_fx: {e}")
    return {"USD": 83.5, "EUR": 90.2}

# ── Instrument Cache ──────────────────────────────────────────────

def get_instrument_by_etoro_id(instrument_id: int) -> Optional[Dict]:
    """Look up instrument by eToro instrumentID. Returns None if not cached."""
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT symbol, name, full_name, asset_type, asset_class_id, currency
                    FROM instruments WHERE instrument_id = %s
                """, (instrument_id,))
                r = cur.fetchone()
                if r:
                    return {"symbol": r[0], "name": r[1], "full_name": r[2],
                            "asset_type": r[3], "asset_class_id": r[4], "currency": r[5]}
    except Exception as e:
        print(f"[DB] get_instrument_by_etoro_id {instrument_id}: {e}")
    return None

def get_missing_etoro_ids(instrument_ids: List[int]) -> List[int]:
    """Return only those IDs not yet in the instruments table."""
    if not instrument_ids:
        return []
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT instrument_id FROM instruments
                    WHERE instrument_id = ANY(%s)
                """, (instrument_ids,))
                cached = {r[0] for r in cur.fetchall()}
                return [i for i in instrument_ids if i not in cached]
    except Exception as e:
        print(f"[DB] get_missing_etoro_ids: {e}")
        return instrument_ids

def upsert_instrument(instrument_id: Optional[int], symbol: str, name: str,
                       full_name: str = None, asset_type: str = "stock",
                       asset_class_id: int = None, currency: str = "USD",
                       exchange: str = None, source: str = "etoro"):
    """Save or update instrument in cache."""
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    INSERT INTO instruments
                      (instrument_id, symbol, name, full_name, asset_type,
                       asset_class_id, currency, exchange, source, fetched_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (source, symbol) DO UPDATE SET
                      name=EXCLUDED.name, full_name=EXCLUDED.full_name,
                      asset_type=EXCLUDED.asset_type, currency=EXCLUDED.currency,
                      fetched_at=NOW()
                """, (instrument_id, symbol, name, full_name, asset_type,
                      asset_class_id, currency, exchange, source))
    except Exception as e:
        print(f"[DB] upsert_instrument {symbol}: {e}")

def get_all_etoro_instruments() -> Dict[int, Dict]:
    """Load all cached eToro instruments as {instrument_id: {...}}."""
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT instrument_id, symbol, name, asset_type, asset_class_id, currency
                    FROM instruments WHERE instrument_id IS NOT NULL
                """)
                return {
                    r[0]: {"symbol": r[1], "name": r[2],
                           "asset_type": r[3], "type": r[4], "currency": r[5]}
                    for r in cur.fetchall()
                }
    except Exception as e:
        print(f"[DB] get_all_etoro_instruments: {e}")
        return {}

def get_instruments_by_source(source: str) -> Dict[str, Dict]:
    """Load cached instruments by source as {symbol: {...}}."""
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT symbol, name, asset_type, currency
                    FROM instruments WHERE source = %s
                """, (source,))
                return {r[0]: {"name": r[1], "asset_type": r[2], "currency": r[3]}
                        for r in cur.fetchall()}
    except Exception as e:
        print(f"[DB] get_instruments_by_source: {e}")
        return {}

# ── eToro Copy Traders ────────────────────────────────────────────

def upsert_copy_traders(mirrors: list, owner: str):
    """Save/update copy trader relationships."""
    try:
        with _conn() as con:
            with con.cursor() as cur:
                for m in mirrors:
                    cur.execute("""
                        INSERT INTO etoro_copy_traders
                          (owner, mirror_id, trader_username, trader_cid,
                           initial_investment, deposit_summary, withdrawal_summary,
                           available_amount, is_paused, started_copy_date, last_seen)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (owner, mirror_id) DO UPDATE SET
                          trader_username   = EXCLUDED.trader_username,
                          deposit_summary   = EXCLUDED.deposit_summary,
                          available_amount  = EXCLUDED.available_amount,
                          is_paused         = EXCLUDED.is_paused,
                          last_seen         = CURRENT_DATE
                    """, (
                        owner,
                        m.get("mirrorID"),
                        m.get("parentUsername"),
                        m.get("parentCID"),
                        m.get("initialInvestment", 0),
                        m.get("depositSummary", 0),
                        m.get("withdrawalSummary", 0),
                        m.get("availableAmount", 0),
                        m.get("isPaused", False),
                        m.get("startedCopyDate"),
                        date.today(),
                    ))
    except Exception as e:
        print(f"[DB] upsert_copy_traders: {e}")

def get_copy_traders(owner: str) -> List[Dict]:
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT mirror_id, trader_username, initial_investment,
                           deposit_summary, available_amount, is_paused, started_copy_date
                    FROM etoro_copy_traders WHERE owner=%s ORDER BY deposit_summary DESC
                """, (owner,))
                cols = ["mirror_id","trader","initial","deposited","available","paused","since"]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as e:
        print(f"[DB] get_copy_traders: {e}")
        return []

# ── Snapshots ─────────────────────────────────────────────────────

def save_portfolio_snapshot(owner: str, broker: Optional[str], sub_account: Optional[str],
                             total_value_inr: float, total_invested_inr: float,
                             total_pnl_inr: float, fx_usd_inr: float=83.5, fx_eur_inr: float=90.2):
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    INSERT INTO portfolio_snapshots
                      (snapshot_date, owner, broker, sub_account,
                       total_value_inr, total_invested_inr, total_pnl_inr,
                       fx_usd_inr, fx_eur_inr)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (snapshot_date, owner, broker, sub_account)
                    DO UPDATE SET
                      total_value_inr    = EXCLUDED.total_value_inr,
                      total_invested_inr = EXCLUDED.total_invested_inr,
                      total_pnl_inr      = EXCLUDED.total_pnl_inr,
                      created_at         = NOW()
                """, (date.today(), owner, broker, sub_account,
                      total_value_inr, total_invested_inr, total_pnl_inr,
                      fx_usd_inr, fx_eur_inr))
    except Exception as e:
        print(f"[DB] save_portfolio_snapshot ({owner}/{broker}/{sub_account}): {e}")

def save_holdings_snapshot(holdings: list, sub_account: str = None):
    if not holdings:
        return
    try:
        with _conn() as con:
            with con.cursor() as cur:
                for h in holdings:
                    cur.execute("""
                        INSERT INTO holdings_history
                          (snapshot_date, owner, broker, sub_account, symbol,
                           asset_type, quantity, avg_price, current_price,
                           current_value, invested_value, pnl, pnl_percent, currency)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (snapshot_date, owner, broker, sub_account, symbol)
                        DO UPDATE SET
                          current_price = EXCLUDED.current_price,
                          current_value = EXCLUDED.current_value,
                          pnl           = EXCLUDED.pnl,
                          pnl_percent   = EXCLUDED.pnl_percent,
                          quantity      = EXCLUDED.quantity,
                          created_at    = NOW()
                    """, (
                        date.today(),
                        getattr(h, "owner", "selvam"),
                        h.broker.value if hasattr(h.broker, "value") else h.broker,
                        sub_account or getattr(h, "sub_account", None),
                        h.symbol,
                        h.asset_type.value if hasattr(h.asset_type, "value") else h.asset_type,
                        h.quantity, h.average_price, h.current_price,
                        h.current_value, h.invested_value, h.pnl, h.pnl_percent,
                        h.currency,
                    ))
        print(f"[DB] Saved {len(holdings)} holdings")
    except Exception as e:
        print(f"[DB] save_holdings_snapshot: {e}")

def save_bonds_snapshot(bonds: list):
    if not bonds:
        return
    try:
        with _conn() as con:
            with con.cursor() as cur:
                for b in bonds:
                    cur.execute("""
                        INSERT INTO bonds_history
                          (snapshot_date, owner, isin, symbol, name,
                           principal_amount, coupon_rate, ytm, ytc,
                           maturity_date, call_date, currency)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (snapshot_date, isin) DO UPDATE SET
                          principal_amount = EXCLUDED.principal_amount,
                          ytm              = EXCLUDED.ytm,
                          created_at       = NOW()
                    """, (
                        date.today(),
                        getattr(b, "owner", "radhika"),
                        b.isin, b.symbol, b.name,
                        b.principal_amount, b.coupon_rate, b.ytm, b.ytc,
                        b.maturity_date, b.call_date, b.currency,
                    ))
        print(f"[DB] Saved {len(bonds)} bonds")
    except Exception as e:
        print(f"[DB] save_bonds_snapshot: {e}")

# ── History Queries ───────────────────────────────────────────────

def get_portfolio_history(owner: str = "combined", days: int = 365) -> List[Dict]:
    try:
        with _conn() as con:
            with con.cursor() as cur:
                if owner == "combined":
                    cur.execute("""
                        SELECT snapshot_date,
                               SUM(total_value_inr)    AS val,
                               SUM(total_invested_inr) AS inv,
                               SUM(total_pnl_inr)      AS pnl
                        FROM portfolio_snapshots
                        WHERE broker IS NULL AND sub_account IS NULL
                          AND snapshot_date >= CURRENT_DATE - %s
                        GROUP BY snapshot_date ORDER BY snapshot_date
                    """, (days,))
                else:
                    cur.execute("""
                        SELECT snapshot_date,
                               SUM(total_value_inr)    AS val,
                               SUM(total_invested_inr) AS inv,
                               SUM(total_pnl_inr)      AS pnl
                        FROM portfolio_snapshots
                        WHERE owner=%s AND broker IS NULL AND sub_account IS NULL
                          AND snapshot_date >= CURRENT_DATE - %s
                        GROUP BY snapshot_date ORDER BY snapshot_date
                    """, (owner, days))
                return [{"date": str(r[0]), "value": round(float(r[1]),2),
                         "invested": round(float(r[2] or 0),2), "pnl": round(float(r[3] or 0),2)}
                        for r in cur.fetchall()]
    except Exception as e:
        print(f"[DB] get_portfolio_history: {e}")
        return []

def get_copy_trader_history(trader_username: str, days: int = 180) -> List[Dict]:
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT snapshot_date, total_value_inr, total_invested_inr, total_pnl_inr
                    FROM portfolio_snapshots
                    WHERE broker='eToro' AND sub_account=%s
                      AND snapshot_date >= CURRENT_DATE - %s
                    ORDER BY snapshot_date
                """, (trader_username, days))
                return [{"date": str(r[0]), "value": float(r[1]),
                         "invested": float(r[2] or 0), "pnl": float(r[3] or 0)}
                        for r in cur.fetchall()]
    except Exception as e:
        print(f"[DB] get_copy_trader_history: {e}")
        return []

def get_symbol_history(symbol: str, days: int = 365) -> List[Dict]:
    try:
        with _conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    SELECT snapshot_date, current_price, current_value, pnl, pnl_percent
                    FROM holdings_history
                    WHERE symbol=%s AND snapshot_date >= CURRENT_DATE - %s
                    ORDER BY snapshot_date
                """, (symbol.upper(), days))
                return [{"date": str(r[0]), "price": float(r[1] or 0), "value": float(r[2] or 0),
                         "pnl": float(r[3] or 0), "pnl_pct": float(r[4] or 0)}
                        for r in cur.fetchall()]
    except Exception as e:
        print(f"[DB] get_symbol_history: {e}")
        return []
