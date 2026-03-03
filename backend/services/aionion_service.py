"""
Aionion Capital Integration — TRaMS Portfolio
Live API: https://dashboard.aionion.com
Auth: Bearer JWT from AIONION_TOKEN (.env)

Token is for Radhika's account (LoginID: R000400).
It expires daily — refresh with: python3 aionion_auth.py

When token is missing/expired the service returns empty holdings
immediately (no network calls, no hanging).
"""
import os, time, base64, json, requests
from typing import List
from dotenv import load_dotenv
from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

ENV_PATH   = os.path.join(os.path.dirname(__file__), "..", ".env")
BASE_URL   = "https://dashboard.aionion.com/api"
_TIMEOUT   = 10          # seconds per request
_CACHE_TTL = 300         # 5 min cache
_cache: dict = {}


# ── Credentials ───────────────────────────────────────────────────
def _creds():
    load_dotenv(ENV_PATH, override=True)
    return {
        "token":   os.getenv("AIONION_TOKEN",   "").strip().strip("'\""),
        "user_id": os.getenv("AIONION_USER_ID", "R000400").strip(),
    }

def _token_valid() -> bool:
    """Return True only if token is present AND not expired. No network call."""
    token = _creds()["token"]
    if not token or not token.startswith("eyJ"):
        return False
    try:
        parts = token.split(".")
        pad   = parts[1] + "=" * (4 - len(parts[1]) % 4)
        exp   = json.loads(base64.b64decode(pad)).get("exp", 0)
        if exp and exp < time.time():
            print("[Aionion] ⚠️  Token expired — run: python3 aionion_auth.py")
            return False
        return True
    except Exception:
        return bool(token)   # can't decode — assume valid and try

def _headers():
    return {
        "Authorization": f"Bearer {_creds()['token']}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

def _get(path: str):
    r = requests.get(f"{BASE_URL}/{path}", headers=_headers(), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


# ── Holdings ──────────────────────────────────────────────────────
def _fetch_equity() -> List[Holding]:
    try:
        data  = _get("Equity/GetEquityHolding")
        items = data if isinstance(data, list) else (data.get("data") or data.get("holdings") or [])
        out   = []
        for item in items:
            sym = (item.get("symbol") or item.get("Symbol") or
                   item.get("scrip")  or item.get("Scrip")  or "").replace("-EQ","").strip()
            qty = float(item.get("quantity")  or item.get("Quantity")  or
                        item.get("holdingUnits") or 0)
            avg = float(item.get("avgCost")   or item.get("AvgCost")   or
                        item.get("purchasePrice") or item.get("avgBuyPrice") or 0)
            ltp = float(item.get("ltp")        or item.get("LTP")       or
                        item.get("currentPrice") or item.get("closePrice") or avg)
            if not sym or qty == 0:
                continue
            inv = round(qty * avg, 2); cur = round(qty * ltp, 2)
            pnl = round(cur - inv, 2)
            out.append(Holding(
                broker=BrokerName.AIONION, symbol=sym,
                name=item.get("companyName") or item.get("CompanyName") or sym,
                asset_type=AssetType.STOCK, quantity=qty,
                average_price=avg, current_price=ltp,
                current_value=cur, invested_value=inv,
                pnl=pnl, pnl_percent=round(pnl/inv*100 if inv else 0, 2),
                exchange=item.get("exchange") or item.get("Exchange") or "NSE",
                currency="INR", owner="radhika",
            ))
        print(f"[Aionion] ✅ Equity: {len(out)} holdings")
        return out
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        if code == 401:
            print("[Aionion] 🔒 Equity 401 — token expired. Run: python3 aionion_auth.py")
        else:
            print(f"[Aionion] Equity HTTP {code}: {e}")
        return []
    except requests.Timeout:
        print("[Aionion] Equity request timed out")
        return []
    except Exception as e:
        print(f"[Aionion] Equity error: {e}")
        return []

def _fetch_mf() -> List[Holding]:
    try:
        data  = _get("MutualFund/GetMFHolding")
        items = data if isinstance(data, list) else (data.get("data") or data.get("holdings") or [])
        out   = []
        for item in items:
            sym   = (item.get("schemeCode") or item.get("symbol") or item.get("Symbol") or "").strip()
            name  =  item.get("schemeName") or item.get("fundName") or item.get("name") or sym
            units = float(item.get("units")       or item.get("Units")    or item.get("quantity") or 0)
            nav   = float(item.get("purchaseNAV") or item.get("avgCost")  or item.get("avgNAV")   or 0)
            cnav  = float(item.get("currentNAV")  or item.get("ltp")      or item.get("currentPrice") or nav)
            if not sym or units == 0:
                continue
            inv = round(units * nav,  2); cur = round(units * cnav, 2)
            pnl = round(cur - inv, 2)
            out.append(Holding(
                broker=BrokerName.AIONION, symbol=sym, name=name,
                asset_type=AssetType.MUTUAL_FUND, quantity=units,
                average_price=nav, current_price=cnav,
                current_value=cur, invested_value=inv,
                pnl=pnl, pnl_percent=round(pnl/inv*100 if inv else 0, 2),
                exchange="NSE", currency="INR", owner="radhika",
            ))
        print(f"[Aionion] ✅ MF: {len(out)} holdings")
        return out
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        if code == 401:
            print("[Aionion] 🔒 MF 401 — token expired. Run: python3 aionion_auth.py")
        else:
            print(f"[Aionion] MF HTTP {code}: {e}")
        return []
    except requests.Timeout:
        print("[Aionion] MF request timed out")
        return []
    except Exception as e:
        print(f"[Aionion] MF error: {e}")
        return []

def _fetch_cash() -> float:
    try:
        data = _get("Dashboard/GetDashboard")
        if isinstance(data, dict):
            return float(data.get("cashBalance") or data.get("cash") or
                         data.get("availableCash") or 0)
    except Exception:
        pass
    return 0.0


# ── Public API ────────────────────────────────────────────────────
def fetch_holdings() -> List[Holding]:
    now    = time.time()
    cached = _cache.get("holdings")
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    # Guard: don't make any network calls if token is invalid
    if not _token_valid():
        print("[Aionion] No valid token — returning empty. Run: python3 aionion_auth.py")
        return []

    result = _fetch_equity() + _fetch_mf()
    _cache["holdings"] = {"ts": now, "data": result}
    return result

def fetch_holdings_from_csv(csv_content: str = None) -> List[Holding]:
    """Called by portfolio_service — CSV upload path or live API."""
    if csv_content is not None:
        return _parse_csv(csv_content)
    return fetch_holdings()

def fetch_summary() -> BrokerSummary:
    connected = _token_valid()
    holdings  = fetch_holdings() if connected else []

    cash = 0.0
    if connected and holdings:
        cash = _cache.get("cash") or _fetch_cash()
        _cache["cash"] = cash

    tv = sum(h.current_value  for h in holdings)
    ti = sum(h.invested_value for h in holdings)
    tp = tv - ti
    return BrokerSummary(
        broker=BrokerName.AIONION,
        connected=connected and bool(holdings),
        total_value=round(tv, 2),
        total_invested=round(ti, 2),
        total_pnl=round(tp, 2),
        total_pnl_percent=round(tp/ti*100 if ti else 0, 2),
        cash_balance=round(cash, 2),
        holdings_count=len(holdings),
        currency="INR",
        owner="radhika",
    )


# ── CSV fallback (for /api/aionion/upload endpoint) ───────────────
def _parse_csv(csv_content: str) -> List[Holding]:
    import csv, io
    holdings = []
    reader = csv.DictReader(io.StringIO(csv_content))
    for row in reader:
        try:
            sym = row.get("Scrip", row.get("Symbol", "")).strip()
            qty = float(row.get("Quantity", row.get("Units", 0)))
            avg = float(row.get("Avg Cost", row.get("Purchase NAV", 0)))
            ltp = float(row.get("LTP", row.get("Current NAV", 0)))
            if not sym or qty == 0:
                continue
            inv = qty * avg; cur = qty * ltp; pnl = cur - inv
            holdings.append(Holding(
                broker=BrokerName.AIONION, symbol=sym,
                name=row.get("Company", sym),
                asset_type=_map_asset_type(row.get("Asset Type", "EQ")),
                quantity=qty, average_price=avg, current_price=ltp,
                current_value=cur, invested_value=inv,
                pnl=pnl, pnl_percent=(pnl/inv*100) if inv else 0,
                exchange=row.get("Exchange", "NSE"), currency="INR", owner="radhika",
            ))
        except (ValueError, KeyError):
            continue
    return holdings

def _map_asset_type(t: str) -> AssetType:
    return {"EQ": AssetType.STOCK, "MF": AssetType.MUTUAL_FUND,
            "ETF": AssetType.ETF, "BOND": AssetType.BOND
            }.get((t or "").upper(), AssetType.STOCK)
