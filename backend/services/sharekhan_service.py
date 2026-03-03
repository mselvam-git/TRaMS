"""
Sharekhan TradeSmart API Integration — TRaMS Portfolio
Docs: https://www.sharekhan.com/trading-api/documentation/login-and-user-details
Owner: Selvam  (customer_id: 208083)

Auth flow:
  1. Run: sudo python3 sharekhan_auth.py   (needs port 80 for OAuth redirect)
  2. Completes OAuth → saves SHAREKHAN_ACCESS_TOKEN to .env → restarts backend
  3. Token expires daily — rerun each morning

Holdings API: sk.holdings(customer_id)
  → tradingSymbol, companyName, aval (quantity), holdPrice (avg price), exchange
LTP via yfinance (NSE symbols with .NS suffix)
"""
import os
import time
from typing import List
from dotenv import load_dotenv
from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

ENV_PATH  = os.path.join(os.path.dirname(__file__), "..", ".env")
_ltp_cache = {"data": {}, "ts": 0}
_CACHE_TTL = 300   # 5 min LTP cache

def _get_creds():
    """Always reload .env so fresh access_token is picked up after auth."""
    load_dotenv(ENV_PATH, override=True)
    return {
        "api_key":      os.getenv("SHAREKHAN_API_KEY", "").strip().strip("'\""),
        "access_token": os.getenv("SHAREKHAN_ACCESS_TOKEN", "").strip().strip("'\""),
        "customer_id":  os.getenv("SHAREKHAN_CUSTOMER_ID", "208083").strip().strip("'\""),
    }

def _get_sk():
    """Return authenticated SharekhanConnect client."""
    try:
        from SharekhanApi.sharekhanConnect import SharekhanConnect
    except ImportError:
        raise RuntimeError("Run: pip3 install SharekhanApi")
    creds = _get_creds()
    return SharekhanConnect(api_key=creds["api_key"], access_token=creds["access_token"])

def _fetch_ltp(symbols: list) -> dict:
    """Get live prices via yfinance with caching."""
    global _ltp_cache
    now = time.time()
    if _ltp_cache["data"] and (now - _ltp_cache["ts"]) < _CACHE_TTL:
        print(f"[Sharekhan] Using cached LTP ({int(now - _ltp_cache['ts'])}s old)")
        return _ltp_cache["data"]
    result = {}
    try:
        import yfinance as yf
        # Sharekhan uses NSE symbols — append .NS for yfinance
        yf_map = {s + ".NS": s for s in symbols if s}
        if not yf_map:
            return {}
        data   = yf.download(list(yf_map.keys()), period="1d", progress=False, auto_adjust=True)
        if not data.empty:
            closes = data["Close"].iloc[-1] if len(yf_map) > 1 else {list(yf_map.keys())[0]: data["Close"].iloc[-1]}
            for yf_sym, orig in yf_map.items():
                if yf_sym in closes and str(closes[yf_sym]) != "nan":
                    result[orig] = float(closes[yf_sym])
        print(f"[Sharekhan] LTP: {len(result)}/{len(symbols)} symbols resolved")
    except Exception as e:
        print(f"[Sharekhan] LTP fetch failed: {e}")
    _ltp_cache = {"data": result, "ts": now}
    return result

def fetch_holdings() -> List[Holding]:
    creds = _get_creds()
    if not creds["access_token"]:
        print("[Sharekhan] No access token — run: sudo python3 sharekhan_auth.py")
        return []
    try:
        sk   = _get_sk()
        raw  = sk.holdings(creds["customer_id"])
        items = raw.get("data") or []
        if not items:
            print(f"[Sharekhan] No holdings returned: {raw}")
            return []
        print(f"[Sharekhan] ✅ Fetched {len(items)} holdings")
        # Collect symbols for LTP lookup
        symbols = [
            item.get("tradingSymbol", "").replace("-EQ", "").replace("-BE", "")
            for item in items if item.get("tradingSymbol")
        ]
        ltp_map = _fetch_ltp(symbols)
        return _parse(items, ltp_map)
    except Exception as e:
        print(f"[Sharekhan] Error: {e}")
        if "access_token" in str(e).lower() or "invalid" in str(e).lower() or "expire" in str(e).lower():
            print("[Sharekhan] ⚠️  Token expired — run: sudo python3 sharekhan_auth.py")
        import traceback; traceback.print_exc()
        return []

def _parse(raw: list, ltp_map: dict = {}) -> List[Holding]:
    holdings = []
    for item in raw:
        raw_sym  = item.get("tradingSymbol") or ""
        symbol   = raw_sym.replace("-EQ", "").replace("-BE", "")
        # Sharekhan: 'aval' = available qty, 'dp' = demat pool qty
        qty  = float(item.get("aval") or item.get("dp") or item.get("quantity") or 0)
        avg  = float(item.get("holdPrice") or item.get("averagePrice") or 0)
        if qty == 0:
            continue
        ltp  = ltp_map.get(symbol) or avg   # fallback to avg if LTP unavailable
        invested = round(qty * avg, 2)
        current  = round(qty * ltp, 2)
        pnl      = round(current - invested, 2)
        # Detect ETF
        asset_type = AssetType.ETF if any(
            kw in symbol.upper() for kw in ["BEES", "IETF", "ETF", "NIFTY", "GOLD"]
        ) else AssetType.STOCK
        holdings.append(Holding(
            broker=BrokerName.SHAREKHAN,
            symbol=symbol,
            name=item.get("companyName") or symbol,
            asset_type=asset_type,
            quantity=qty,
            average_price=avg,
            current_price=ltp,
            current_value=current,
            invested_value=invested,
            pnl=pnl,
            pnl_percent=round((pnl / invested * 100) if invested else 0, 2),
            exchange=item.get("exchange") or "NSE",
            currency="INR",
            owner="selvam",
        ))
    return holdings

def fetch_summary() -> BrokerSummary:
    creds          = _get_creds()
    connected      = bool(creds["access_token"])
    holdings       = fetch_holdings()
    total_value    = sum(h.current_value for h in holdings)
    total_invested = sum(h.invested_value for h in holdings)
    total_pnl      = total_value - total_invested
    return BrokerSummary(
        broker=BrokerName.SHAREKHAN,
        connected=connected,
        total_value=round(total_value, 2),
        total_invested=round(total_invested, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round((total_pnl / total_invested * 100) if total_invested else 0, 2),
        cash_balance=0.0,
        holdings_count=len(holdings),
        currency="INR",
        owner="selvam",
    )
