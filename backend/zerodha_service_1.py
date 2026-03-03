"""
Zerodha Kite Connect Integration
Docs: https://kite.trade/docs/connect/v3/
"""
import os
from typing import List
from dotenv import load_dotenv
from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

ASSET_TYPE_MAP = {
    "EQ":  AssetType.STOCK,
    "MF":  AssetType.MUTUAL_FUND,
    "ETF": AssetType.ETF,
    "OPT": AssetType.OPTION,
}

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def _get_credentials():
    """Reload .env fresh on every call — picks up new tokens without restart."""
    load_dotenv(ENV_PATH, override=True)
    api_key      = os.getenv("ZERODHA_API_KEY", "").strip().strip("'\"")
    access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "").strip().strip("'\"")
    return api_key, access_token


def _get_kite():
    """Return an authenticated KiteConnect client."""
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        raise RuntimeError("Run: pip3 install kiteconnect")
    api_key, access_token = _get_credentials()
    if not api_key or not access_token:
        raise RuntimeError("ZERODHA_API_KEY or ZERODHA_ACCESS_TOKEN missing in .env")
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def _is_mock() -> bool:
    api_key, access_token = _get_credentials()
    return not (api_key and access_token)


def fetch_holdings() -> List[Holding]:
    if _is_mock():
        print("[Zerodha] No credentials found — using mock data")
        return _parse_holdings(_mock_raw_holdings())
    try:
        kite = _get_kite()
        raw  = kite.holdings()
        print(f"[Zerodha] Fetched {len(raw)} real holdings")
        return _parse_holdings(raw)
    except Exception as e:
        print(f"[Zerodha] Error: {e} — falling back to mock")
        return _parse_holdings(_mock_raw_holdings())


def _parse_holdings(raw: list) -> List[Holding]:
    holdings = []
    for item in raw:
        qty      = item.get("quantity", 0)
        avg      = item.get("average_price", 0)
        ltp      = item.get("last_price", 0)
        invested = qty * avg
        current  = qty * ltp
        pnl      = current - invested
        holdings.append(Holding(
            broker=BrokerName.ZERODHA,
            symbol=item["tradingsymbol"],
            name=item.get("company", item.get("tradingsymbol", "")),
            asset_type=ASSET_TYPE_MAP.get(item.get("instrument_type", "EQ"), AssetType.STOCK),
            quantity=qty,
            average_price=avg,
            current_price=ltp,
            current_value=round(current, 2),
            invested_value=round(invested, 2),
            pnl=round(pnl, 2),
            pnl_percent=round((pnl / invested * 100) if invested else 0, 2),
            exchange=item.get("exchange"),
        ))
    return holdings


def fetch_summary() -> BrokerSummary:
    holdings       = fetch_holdings()
    total_value    = sum(h.current_value for h in holdings)
    total_invested = sum(h.invested_value for h in holdings)
    total_pnl      = total_value - total_invested
    cash_balance   = 0.0
    connected      = not _is_mock()

    if connected:
        try:
            kite         = _get_kite()
            margins      = kite.margins()
            cash_balance = margins.get("equity", {}).get("available", {}).get("cash", 0.0)
        except Exception as e:
            print(f"[Zerodha] Could not fetch margins: {e}")

    return BrokerSummary(
        broker=BrokerName.ZERODHA,
        connected=connected,
        total_value=round(total_value, 2),
        total_invested=round(total_invested, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round((total_pnl / total_invested * 100) if total_invested else 0, 2),
        cash_balance=cash_balance,
        holdings_count=len(holdings),
    )


def _mock_raw_holdings():
    return [
        {"tradingsymbol": "RELIANCE", "company": "Reliance Industries",
         "exchange": "NSE", "quantity": 10, "average_price": 2400.0,
         "last_price": 2650.0, "instrument_type": "EQ"},
        {"tradingsymbol": "INFY", "company": "Infosys Ltd",
         "exchange": "NSE", "quantity": 25, "average_price": 1380.0,
         "last_price": 1520.0, "instrument_type": "EQ"},
        {"tradingsymbol": "HDFCBANK", "company": "HDFC Bank",
         "exchange": "NSE", "quantity": 15, "average_price": 1600.0,
         "last_price": 1720.0, "instrument_type": "EQ"},
        {"tradingsymbol": "NIFTYBEES", "company": "Nippon India ETF Nifty BeES",
         "exchange": "NSE", "quantity": 100, "average_price": 220.0,
         "last_price": 245.0, "instrument_type": "ETF"},
    ]
