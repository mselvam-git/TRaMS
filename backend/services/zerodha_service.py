"""
Zerodha Kite Connect Integration — TRaMS Portfolio
Docs: https://kite.trade/docs/connect/v3/
Owner: Selvam

Auth flow:
  1. Run: python3 zerodha_auth.py   (opens browser, exchanges token, saves to .env)
  2. Token expires daily at 6am IST — rerun zerodha_auth.py each morning

Holdings API: GET /portfolio/holdings
  → tradingsymbol, exchange, quantity, average_price, last_price, pnl, isin
Margins  API: GET /user/margins
  → equity.available.cash
"""
import os
from typing import List
from dotenv import load_dotenv
from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")

ASSET_TYPE_MAP = {
    "EQ":  AssetType.STOCK,
    "MF":  AssetType.MUTUAL_FUND,
    "ETF": AssetType.ETF,
    "OPT": AssetType.OPTION,
}

def _get_creds():
    """Always reload .env so fresh access_token is used after zerodha_auth.py runs."""
    load_dotenv(ENV_PATH, override=True)
    return {
        "api_key":      os.getenv("ZERODHA_API_KEY", "").strip(),
        "access_token": os.getenv("ZERODHA_ACCESS_TOKEN", "").strip().strip("'\""),
    }

def _get_kite():
    """Return authenticated KiteConnect client."""
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        raise RuntimeError("Run: pip3 install kiteconnect")
    creds = _get_creds()
    kite  = KiteConnect(api_key=creds["api_key"])
    kite.set_access_token(creds["access_token"])
    return kite

def fetch_holdings() -> List[Holding]:
    creds = _get_creds()
    if not creds["api_key"] or not creds["access_token"]:
        print("[Zerodha] No credentials — run: python3 zerodha_auth.py")
        return []
    try:
        kite = _get_kite()
        raw  = kite.holdings()
        print(f"[Zerodha] ✅ Fetched {len(raw)} holdings")
        return _parse_holdings(raw)
    except Exception as e:
        print(f"[Zerodha] Error: {e}")
        if "access_token" in str(e).lower() or "token" in str(e).lower():
            print("[Zerodha] ⚠️  Token expired — run: python3 zerodha_auth.py")
        return []

def _parse_holdings(raw: list) -> List[Holding]:
    holdings = []
    for item in raw:
        qty  = item.get("quantity", 0)
        avg  = item.get("average_price", 0)
        ltp  = item.get("last_price", 0)
        # Use Zerodha's own pnl field if available, else calculate
        pnl  = item.get("pnl") if item.get("pnl") is not None else (qty * ltp) - (qty * avg)
        invested = round(qty * avg, 2)
        current  = round(qty * ltp, 2)
        # Map instrument type — Zerodha uses instrument_type field
        inst_type = item.get("instrument_type", "EQ")
        # Detect ETF by tradingsymbol suffix common patterns
        symbol = item.get("tradingsymbol", "")
        if any(kw in symbol.upper() for kw in ["BEES", "IETF", "ETF"]):
            inst_type = "ETF"
        holdings.append(Holding(
            broker=BrokerName.ZERODHA,
            symbol=symbol,
            name=item.get("company") or item.get("name") or symbol,
            asset_type=ASSET_TYPE_MAP.get(inst_type, AssetType.STOCK),
            quantity=qty,
            average_price=round(avg, 4),
            current_price=round(ltp, 4),
            current_value=current,
            invested_value=invested,
            pnl=round(pnl, 2),
            pnl_percent=round((pnl / invested * 100) if invested else 0, 2),
            exchange=item.get("exchange", "NSE"),
            currency="INR",
            owner="selvam",
            day_change=item.get("day_change"),
            day_change_percent=item.get("day_change_percentage"),
        ))
    return holdings

def fetch_summary() -> BrokerSummary:
    creds    = _get_creds()
    holdings = fetch_holdings()
    connected = bool(creds["api_key"] and creds["access_token"])
    total_value    = sum(h.current_value for h in holdings)
    total_invested = sum(h.invested_value for h in holdings)
    total_pnl      = total_value - total_invested
    cash_balance   = 0.0
    if connected and holdings:
        try:
            kite    = _get_kite()
            margins = kite.margins()
            cash_balance = float(
                margins.get("equity", {}).get("available", {}).get("cash", 0) or 0
            )
        except Exception as e:
            print(f"[Zerodha] Margins error: {e}")
    return BrokerSummary(
        broker=BrokerName.ZERODHA,
        connected=connected,
        total_value=round(total_value, 2),
        total_invested=round(total_invested, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round((total_pnl / total_invested * 100) if total_invested else 0, 2),
        cash_balance=cash_balance,
        holdings_count=len(holdings),
        currency="INR",
        owner="selvam",
    )
