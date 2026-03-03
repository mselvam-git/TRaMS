"""
Interactive Brokers TWS Integration — TRaMS Portfolio
=======================================================
Uses ibapi (official IBKR Python API) to connect directly to TWS.

Requirements:
  - TWS (Trader Workstation) must be running
  - API connections must be enabled in TWS:
      Global Configuration → API → Settings
      ✓ Enable ActiveX and Socket Clients
      ✓ Socket port: 7496  (live) or 7497 (paper)
      ✓ Trusted IPs: 127.0.0.1

Accounts connected:
  U15214441 — Selvam
  U20199465 — Selvam (second account)
  F17906466 — Financial advisor umbrella (ignored if empty)

Strategy:
  - Background thread refreshes data every REFRESH_INTERVAL seconds
  - API calls always return from cache instantly (never block)
  - First request triggers a background fetch; stale cache is served meanwhile
"""

import os, threading, time, logging
from typing import List, Dict, Optional
from dotenv import load_dotenv
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract as IbContract
    _IBAPI_AVAILABLE = True
except ImportError:
    _IBAPI_AVAILABLE = False
    EClient = object
    EWrapper = object

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)
from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

log = logging.getLogger("ibkr")

# ── Config ────────────────────────────────────────────────────────
TWS_HOST      = os.getenv("TWS_HOST",      "127.0.0.1")
TWS_PORT      = int(os.getenv("TWS_PORT",  "7496"))
TWS_CLIENT_ID = int(os.getenv("TWS_CLIENT_ID", "20"))
REFRESH_INTERVAL = 180   # seconds between background refreshes

IBKR_ACCOUNTS = [
    a.strip()
    for a in os.getenv("IBKR_ACCOUNTS", os.getenv("IBKR_ACCOUNT_ID", "")).split(",")
    if a.strip()
]
_SKIP_ACCOUNTS = {"F17906466"}
_ACCOUNT_OWNER = {
    "U15214441": "selvam",
    "U20199465": "selvam",
}

# ── Cache & background state ──────────────────────────────────────
_cache_lock   = threading.Lock()
_cached_holdings: List[Holding] = []
_cached_cash:     float = 0.0
_cache_ts:        float = 0.0
_fetch_in_progress = False
_tws_connected:    bool = False


# ── IBKR App ──────────────────────────────────────────────────────
class _IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.positions:    List[dict] = []
        self.pnl_map:      Dict[int, dict] = {}
        self.acct_values:  Dict[tuple, tuple] = {}
        self._acct_ready   = threading.Event()
        self._pos_done     = threading.Event()
        self._acct_sum_done= threading.Event()
        self._conn_error:  Optional[str] = None

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode in (2104,2106,2107,2108,2119,2158,2103,10197,2100):
            return
        log.warning(f"[IBKR] {reqId}/{errorCode}: {errorString}")
        if errorCode in (502, 501, 504, 1100, 1300):
            self._conn_error = errorString

    def managedAccounts(self, accountsList: str):
        self.all_accounts = [a.strip() for a in accountsList.split(",") if a.strip()]
        self._acct_ready.set()

    def position(self, account: str, contract: IbContract, position: float, avgCost: float):
        if account in _SKIP_ACCOUNTS or position == 0:
            return
        self.positions.append({
            "account":  account,
            "symbol":   contract.symbol,
            "secType":  contract.secType,
            "exchange": contract.primaryExchange or contract.exchange,
            "currency": contract.currency,
            "conId":    contract.conId,
            "position": float(position),
            "avgCost":  float(avgCost),
        })

    def positionEnd(self):
        self._pos_done.set()

    def pnlSingle(self, reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value):
        self.pnl_map[reqId] = {
            "unrealizedPnL": float(unrealizedPnL),
            "value":         float(value),
        }

    def accountSummary(self, reqId, account, tag, value, currency):
        self.acct_values[(account, tag)] = (value, currency)

    def accountSummaryEnd(self, reqId):
        self._acct_sum_done.set()


def _do_fetch() -> None:
    """Run in background thread. Connects to TWS, fetches all data, updates cache."""
    global _cached_holdings, _cached_cash, _cache_ts, _fetch_in_progress, _tws_connected

    try:
        app = _IBApp()
        app.connect(TWS_HOST, TWS_PORT, clientId=TWS_CLIENT_ID)
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()

        if not app._acct_ready.wait(timeout=6):
            app.disconnect()
            print(f"[IBKR] TWS not responding on {TWS_HOST}:{TWS_PORT}")
            _tws_connected = False
            return

        if app._conn_error:
            app.disconnect()
            print(f"[IBKR] Connection error: {app._conn_error}")
            _tws_connected = False
            return

        _tws_connected = True

        # 1. Positions
        app.reqPositions()
        app._pos_done.wait(timeout=12)
        try:
            app.cancelPositions()
        except Exception:
            pass

        # 2. PnL per position (live market value)
        req_map = {}
        for i, pos in enumerate(app.positions):
            rid = 2000 + i
            app.reqPnLSingle(rid, pos["account"], "", pos["conId"])
            req_map[rid] = i

        wait_secs = min(max(len(app.positions) * 0.12, 2), 15)
        time.sleep(wait_secs)

        for rid in req_map:
            try:
                app.cancelPnLSingle(rid)
            except Exception:
                pass

        # 3. Account summary (cash)
        app.reqAccountSummary(9001, "All",
            "NetLiquidation,TotalCashValue,UnrealizedPnL,GrossPositionValue")
        app._acct_sum_done.wait(timeout=8)

        # Attach PnL to positions
        for rid, idx in req_map.items():
            if rid in app.pnl_map:
                app.positions[idx]["pnl_data"] = app.pnl_map[rid]

        app.disconnect()
        thread.join(timeout=3)

        holdings = _parse_positions(app)
        cash     = sum(
            float(v) for (acct, tag), (v, _) in app.acct_values.items()
            if tag == "TotalCashValue" and acct not in _SKIP_ACCOUNTS
        )

        with _cache_lock:
            _cached_holdings = holdings
            _cached_cash     = cash
            _cache_ts        = time.time()

        print(f"[IBKR] ✅ Fetched {len(holdings)} positions  cash=${cash:.2f}")

    except Exception as e:
        print(f"[IBKR] Fetch error: {e}")
        import traceback; traceback.print_exc()
    finally:
        _fetch_in_progress = False


def _ensure_fresh(force: bool = False) -> None:
    """Trigger a background refresh if cache is stale and none is running."""
    global _fetch_in_progress
    now = time.time()
    stale = (now - _cache_ts) > REFRESH_INTERVAL
    if (stale or force) and not _fetch_in_progress:
        _fetch_in_progress = True
        t = threading.Thread(target=_do_fetch, daemon=True)
        t.name = "ibkr-refresh"
        t.start()


def _tws_port_open() -> bool:
    import socket
    s = socket.socket()
    s.settimeout(1)
    ok = s.connect_ex((TWS_HOST, TWS_PORT)) == 0
    s.close()
    return ok


# ── Public API ────────────────────────────────────────────────────
def fetch_holdings() -> List[Holding]:
    """
    Return cached IBKR holdings instantly. Triggers background refresh if stale.
    Never blocks the caller.
    """
    _ensure_fresh()
    with _cache_lock:
        return list(_cached_holdings)


def fetch_summary() -> BrokerSummary:
    _ensure_fresh()
    with _cache_lock:
        holdings = list(_cached_holdings)
        cash     = _cached_cash
        ts       = _cache_ts

    connected      = _tws_connected or _tws_port_open()
    total_value    = sum(h.current_value  for h in holdings)
    total_invested = sum(h.invested_value for h in holdings)
    total_pnl      = total_value - total_invested

    return BrokerSummary(
        broker=BrokerName.INTERACTIVE_BROKERS,
        connected=connected,
        total_value=round(total_value, 2),
        total_invested=round(total_invested, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round(total_pnl / total_invested * 100 if total_invested else 0, 2),
        cash_balance=round(cash, 2),
        holdings_count=len(holdings),
        currency="USD",
        owner="selvam",
    )


# ── Parsing ───────────────────────────────────────────────────────
def _parse_positions(app: _IBApp) -> List[Holding]:
    holdings = []
    for pos in app.positions:
        qty      = pos["position"]
        avg_cost = pos["avgCost"]
        pnl_d    = pos.get("pnl_data", {})
        account  = pos["account"]

        mkt_val = float(pnl_d.get("value", 0)) or (qty * avg_cost)
        unreal  = float(pnl_d.get("unrealizedPnL", 0))
        mkt_px  = (mkt_val / qty) if qty else avg_cost

        invested = round(qty * avg_cost, 2)
        current  = round(mkt_val, 2)
        pnl      = round(unreal if unreal else (current - invested), 2)

        holdings.append(Holding(
            broker=BrokerName.INTERACTIVE_BROKERS,
            symbol=pos["symbol"],
            name=pos["symbol"],
            asset_type=_map_asset_type(pos["secType"]),
            quantity=qty,
            average_price=round(avg_cost, 4),
            current_price=round(mkt_px,   4),
            current_value=current,
            invested_value=invested,
            pnl=pnl,
            pnl_percent=round(pnl / invested * 100 if invested else 0, 2),
            currency=pos["currency"],
            exchange=pos["exchange"],
            sub_account=account,
            owner=_ACCOUNT_OWNER.get(account, "selvam"),
        ))
    return holdings


def _map_asset_type(sec_type: str) -> AssetType:
    return {
        "STK":    AssetType.STOCK,
        "ETF":    AssetType.ETF,
        "BOND":   AssetType.BOND,
        "OPT":    AssetType.OPTION,
        "CRYPTO": AssetType.CRYPTO,
        "FUT":    AssetType.OTHER,
        "CASH":   AssetType.OTHER,
    }.get((sec_type or "").upper(), AssetType.OTHER)


# Kick off initial background fetch at import time (only if ibapi is available)
if _IBAPI_AVAILABLE:
    _ensure_fresh()
