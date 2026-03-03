"""
Zerodha Kite Connect Integration
Docs: https://kite.trade/docs/connect/v3/
"""
import os
from typing import List
from dotenv import load_dotenv

# Reload .env each time so fresh access_token is picked up after auth
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

API_KEY      = os.getenv("ZERODHA_API_KEY", "")
ACCESS_TOKEN = os.getenv("ZERODHA_ACCESS_TOKEN", "")

ASSET_TYPE_MAP = {
    "EQ":  AssetType.STOCK,
    "MF":  AssetType.MUTUAL_FUND,
    "ETF": AssetType.ETF,
    "OPT": AssetType.OPTION,
}

USE_MOCK = not (API_KEY and ACCESS_TOKEN)


def _get_kite():
    """Return an authenticated KiteConnect client."""
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        raise RuntimeError("Run: pip3 install kiteconnect")
    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
    return kite


def fetch_holdings() -> List[Holding]:
    if USE_MOCK:
        return _parse_holdings(_mock_raw_holdings())
    try:
        kite = _get_kite()
        raw = kite.holdings()
        return _parse_holdings(raw)
    except Exception as e:
        print(f"[Zerodha] Error fetching holdings: {e} — falling back to mock")
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
            name=item.get("company", item["tradingsymbol"]),
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
    holdings = fetch_holdings()
    total_value    = sum(h.current_value for h in holdings)
    total_invested = sum(h.invested_value for h in holdings)
    total_pnl      = total_value - total_invested
    cash_balance   = 0.0

    if not USE_MOCK:
        try:
            kite    = _get_kite()
            margins = kite.margins()
            cash_balance = margins.get("equity", {}).get("available", {}).get("cash", 0.0)
        except Exception as e:
            print(f"[Zerodha] Error fetching margins: {e}")

    return BrokerSummary(
        broker=BrokerName.ZERODHA,
        connected=not USE_MOCK,
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
