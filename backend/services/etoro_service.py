"""
eToro Service — TRaMS Portfolio
================================
Base URL: https://public-api.etoro.com/api/v1
Auth: x-api-key, x-user-key, x-request-id headers

Selvam  username: amizhthini  → ETORO_PUBLIC_KEY + ETORO_USER_KEY
Radhika username: aadhirai    → ETORO_RADHIKA_PUBLIC_KEY + ETORO_RADHIKA_USER_KEY

Cost basis  = initialAmountInDollars (actual cost, NOT 'amount' which drifts)
Current val = unrealizedPnL.exposureInAccountCurrency
Copy P&L    = sum(unrealizedPnL.pnL) + mirror.closedPositionsNetProfit
"""
import os, uuid, time, json, requests
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
from models.schemas import Holding, BrokerSummary, BrokerName, AssetType

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
BASE_URL = "https://public-api.etoro.com/api/v1"

ASSET_CLASS_MAP = {
    1: AssetType.STOCK, 2: AssetType.STOCK, 3: AssetType.STOCK,
    4: AssetType.ETF,   5: AssetType.STOCK, 6: AssetType.CRYPTO,
    7: AssetType.STOCK, 8: AssetType.ETF,  10: AssetType.CRYPTO,
}
ETORO_USERNAMES = {"selvam": "amizhthini", "radhika": "aadhirai"}

_inst_cache:    Dict[int, Dict] = {}
_pnl_cache:     Dict[str, dict] = {}
_profile_cache: Dict[str, dict] = {}
_gain_cache:    Dict[str, dict] = {}
_PNL_TTL = 120; _PROFILE_TTL = 3600; _GAIN_TTL = 3600

INST_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "etoro_instruments.json")
def _load_inst_file():
    try:
        if os.path.exists(INST_FILE):
            with open(INST_FILE) as f:
                for k, v in json.load(f).items():
                    _inst_cache[int(k)] = v
    except: pass
def _save_inst_file():
    os.makedirs(os.path.dirname(INST_FILE), exist_ok=True)
    try:
        with open(INST_FILE, "w") as f:
            json.dump({str(k): v for k, v in _inst_cache.items()}, f)
    except: pass
_load_inst_file()

def _get_accounts():
    load_dotenv(ENV_PATH, override=True)
    out = []
    pk = os.getenv("ETORO_PUBLIC_KEY","").strip(); uk = os.getenv("ETORO_USER_KEY","").strip()
    if pk and uk: out.append((pk, uk, "selvam"))
    rpk = os.getenv("ETORO_RADHIKA_PUBLIC_KEY","").strip(); ruk = os.getenv("ETORO_RADHIKA_USER_KEY","").strip()
    if rpk and ruk: out.append((rpk, ruk, "radhika"))
    return out

def _h(pk, uk): return {"x-api-key": pk, "x-user-key": uk, "x-request-id": str(uuid.uuid4()), "Accept": "application/json"}

def _fetch_pnl(pk, uk, owner):
    c = _pnl_cache.get(owner); now = time.time()
    if c and (now - c["ts"]) < _PNL_TTL: return c["data"]
    try:
        r = requests.get(f"{BASE_URL}/trading/info/real/pnl", headers=_h(pk, uk), timeout=25)
        r.raise_for_status(); data = r.json()
        _pnl_cache[owner] = {"ts": now, "data": data}
        print(f"[eToro] {owner}: PNL OK ({len(data.get('clientPortfolio',{}).get('positions',[]))} direct, {len(data.get('clientPortfolio',{}).get('mirrors',[]))} mirrors)")
        return data
    except Exception as e:
        print(f"[eToro] {owner}: PNL error: {e}")
        return (c or {}).get("data", {})

def _fetch_profile(pk, uk, username):
    c = _profile_cache.get(username); now = time.time()
    if c and (now - c["ts"]) < _PROFILE_TTL: return c["data"]
    try:
        r = requests.get(f"{BASE_URL}/user-info/people", headers=_h(pk, uk), params={"usernames": username}, timeout=15)
        if r.status_code == 200:
            users = r.json().get("users", [])
            data = users[0] if users else {}
            _profile_cache[username] = {"ts": now, "data": data}; return data
    except Exception as e: print(f"[eToro] profile({username}): {e}")
    return {}

def _fetch_gain(pk, uk, username):
    c = _gain_cache.get(username); now = time.time()
    if c and (now - c["ts"]) < _GAIN_TTL: return c["data"]
    try:
        r = requests.get(f"{BASE_URL}/user-info/people/{username}/gain", headers=_h(pk, uk), timeout=15)
        if r.status_code == 200:
            data = r.json(); _gain_cache[username] = {"ts": now, "data": data}; return data
    except Exception as e: print(f"[eToro] gain({username}): {e}")
    return {}

def _fetch_live_portfolio(pk, uk, username):
    try:
        r = requests.get(f"{BASE_URL}/user-info/people/{username}/portfolio/live", headers=_h(pk, uk), timeout=20)
        if r.status_code == 200: return r.json()
    except Exception as e: print(f"[eToro] live_portfolio({username}): {e}")
    return {}

def _resolve_instruments(ids: List[int], pk: str, uk: str) -> Dict[int, Dict]:
    result  = {i: _inst_cache[i] for i in ids if i in _inst_cache}
    missing = [i for i in ids if i not in _inst_cache]
    if not missing: return result
    print(f"[eToro] Fetching {len(missing)} instruments from API...")
    new_f = False
    for iid in missing:
        try:
            items = []
            r = requests.get(f"{BASE_URL}/market-data/instruments", headers=_h(pk, uk), params={"InstrumentIds": str(iid)}, timeout=10)
            if r.status_code == 200: items = r.json().get("InstrumentDisplayDatas", [])
            if not items:
                r2 = requests.get(f"{BASE_URL}/market-data/search", headers=_h(pk, uk), params={"instrumentId": str(iid)}, timeout=10)
                if r2.status_code == 200: items = r2.json().get("items", [])
            if items:
                inst = items[0]
                sym  = inst.get("symbolFull") or inst.get("internalSymbolFull") or inst.get("symbol") or str(iid)
                name = inst.get("instrumentDisplayName") or inst.get("internalInstrumentDisplayName") or sym
                cid  = inst.get("assetClassId") or inst.get("internalAssetClassId") or 5
                curr = inst.get("currency", "USD")
                info = {"symbol": sym, "name": name, "cls_id": cid, "currency": curr, "asset_type": ASSET_CLASS_MAP.get(cid, AssetType.STOCK).value}
                _inst_cache[iid] = info; result[iid] = info; new_f = True
            time.sleep(0.08)
        except Exception as e: print(f"[eToro] Inst {iid}: {e}")
    if new_f: _save_inst_file()
    return result

def _parse_positions(positions: list, inst_map: Dict, owner: str, sub_account: str = None) -> List[Holding]:
    grouped: Dict[int, list] = {}
    for pos in positions:
        iid = pos.get("instrumentID") or pos.get("instrumentId")
        if iid: grouped.setdefault(int(iid), []).append(pos)
    holdings = []
    for iid, pl in grouped.items():
        inst       = inst_map.get(iid, {})
        symbol     = inst.get("symbol") or str(iid)
        name       = inst.get("name") or symbol
        cls_id     = inst.get("cls_id", 5)
        asset_type = ASSET_CLASS_MAP.get(cls_id, AssetType.STOCK)
        currency   = inst.get("currency", "USD")
        total_invested = sum(float(p.get("initialAmountInDollars") or p.get("amount") or 0) for p in pl)
        total_value = 0.0
        for p in pl:
            pobj     = p.get("unrealizedPnL") or {}
            exposure = float(pobj.get("exposureInAccountCurrency") or 0)
            if exposure: total_value += exposure
            else:
                cost = float(p.get("initialAmountInDollars") or p.get("amount") or 0)
                total_value += cost + float(pobj.get("pnL") or 0)
        total_pnl   = total_value - total_invested
        total_units = sum(float(p.get("units") or p.get("lotCount") or 0) for p in pl)
        first   = pl[0]; pobj = first.get("unrealizedPnL") or {}
        cur_px  = float(pobj.get("closeRate") or first.get("openRate") or 0)
        avg_px  = float(first.get("openRate") or 0)
        holdings.append(Holding(
            broker=BrokerName.ETORO, symbol=symbol, name=name, asset_type=asset_type,
            quantity=round(total_units, 6), average_price=round(avg_px, 6),
            current_price=round(cur_px, 6), current_value=round(total_value, 2),
            invested_value=round(total_invested, 2), pnl=round(total_pnl, 2),
            pnl_percent=round((total_pnl/total_invested*100) if total_invested else 0, 2),
            currency=currency, exchange="eToro", owner=owner, sub_account=sub_account,
        ))
    return holdings

def _fetch_account(pk, uk, owner):
    data = _fetch_pnl(pk, uk, owner)
    if not data: return [], [], [], 0.0
    cp = data.get("clientPortfolio", {})
    direct_pos  = cp.get("positions", [])
    mirrors_raw = cp.get("mirrors", [])
    credit      = float(cp.get("credit") or 0)
    all_ids = list(set(
        [int(p["instrumentID"]) for p in direct_pos if p.get("instrumentID")]
        + [int(p["instrumentID"]) for m in mirrors_raw for p in m.get("positions",[]) if p.get("instrumentID")]
    ))
    inst_map = _resolve_instruments([i for i in all_ids if i], pk, uk)
    direct = _parse_positions(direct_pos, inst_map, owner)
    copy_h = []
    for m in mirrors_raw:
        trader = m.get("parentUsername") or f"copy_{m.get('mirrorID','?')}"
        copy_h.extend(_parse_positions(m.get("positions",[]), inst_map, owner, sub_account=trader))
    return direct, copy_h, mirrors_raw, credit

# ── Public API ───────────────────────────────────────────────────────
def fetch_holdings(include_copy: bool = True) -> List[Holding]:
    accounts = _get_accounts()
    if not accounts:
        print("[eToro] No API keys — returning empty holdings")
        return []
    out = []
    for pk, uk, owner in accounts:
        direct, copy_h, _, _ = _fetch_account(pk, uk, owner)
        out.extend(direct)
        if include_copy: out.extend(copy_h)
    return out

def fetch_holdings_from_csv(*args, **kwargs) -> List[Holding]:
    """Backward-compat shim — now calls real API."""
    return fetch_holdings()

def fetch_copy_trader_summary(owner: str = None) -> List[Dict]:
    accounts = _get_accounts(); result = []
    for pk, uk, acc_owner in accounts:
        if owner and acc_owner != owner: continue
        data    = _fetch_pnl(pk, uk, acc_owner)
        mirrors = data.get("clientPortfolio", {}).get("mirrors", [])
        for m in mirrors:
            positions  = m.get("positions", [])
            deposited  = float(m.get("depositSummary")           or 0)
            withdrawn  = float(m.get("withdrawalSummary")        or 0)
            available  = float(m.get("availableAmount")          or 0)
            closed_pnl = float(m.get("closedPositionsNetProfit") or 0)
            pos_value  = 0.0
            for p in positions:
                pobj     = p.get("unrealizedPnL") or {}
                exposure = float(pobj.get("exposureInAccountCurrency") or 0)
                if exposure: pos_value += exposure
                else:
                    cost = float(p.get("initialAmountInDollars") or p.get("amount") or 0)
                    pos_value += cost + float(pobj.get("pnL") or 0)
            unrealized_pnl = sum(float((p.get("unrealizedPnL") or {}).get("pnL") or 0) for p in positions)
            total_pnl = unrealized_pnl + closed_pnl
            result.append({
                "owner": acc_owner, "mirror_id": m.get("mirrorID"),
                "trader": m.get("parentUsername") or "Unknown",
                "trader_cid": m.get("parentCID"), "positions_count": len(positions),
                "deposited": round(deposited, 2), "withdrawn": round(withdrawn, 2),
                "net_invested": round(deposited - withdrawn, 2), "available": round(available, 2),
                "pos_value": round(pos_value, 2), "total_value": round(pos_value + available, 2),
                "unrealized_pnl": round(unrealized_pnl, 2), "closed_pnl": round(closed_pnl, 2),
                "total_pnl": round(total_pnl, 2),
                "pnl_percent": round((total_pnl / deposited * 100) if deposited else 0, 2),
                "is_paused": bool(m.get("isPaused")), "started": (m.get("startedCopyDate") or "")[:10],
            })
    return sorted(result, key=lambda x: -x["deposited"])

def fetch_performance_history(owner: str = None) -> Dict:
    """
    Monthly + yearly gain % from /user-info/people/{username}/gain
    eToro returns gain as a plain float already in % (e.g. 5.23 means +5.23%).
    Do NOT multiply by 100.
    """
    accounts = _get_accounts()
    result = {}
    for pk, uk, acc_owner in accounts:
        if owner and acc_owner != owner:
            continue
        username = ETORO_USERNAMES.get(acc_owner)
        if not username:
            continue
        data = _fetch_gain(pk, uk, username)
        if data:
            result[acc_owner] = {
                "username": username,
                "monthly": [
                    {"date": g["timestamp"][:7], "gain": round(float(g["gain"]), 2)}
                    for g in data.get("monthly", []) if g.get("gain") is not None
                ],
                "yearly": [
                    {"date": g["timestamp"][:4], "gain": round(float(g["gain"]), 2)}
                    for g in data.get("yearly", []) if g.get("gain") is not None
                ],
            }
    return result

def fetch_user_profiles() -> Dict:
    accounts = _get_accounts(); profiles = {}
    for pk, uk, owner in accounts:
        username = ETORO_USERNAMES.get(owner)
        if not username: continue
        prof = _fetch_profile(pk, uk, username)
        if prof:
            profiles[owner] = {
                "username": username, "gcid": prof.get("gcid"),
                "real_cid": prof.get("realCID"), "is_verified": prof.get("isVerified"),
                "country": prof.get("country"), "account_type": prof.get("accountType"),
                "avatar": next((a["url"] for a in prof.get("avatars",[]) if a.get("width")==50), None),
            }
    return profiles

def fetch_summary() -> BrokerSummary:
    accounts = _get_accounts()
    if not accounts:
        return BrokerSummary(broker=BrokerName.ETORO, connected=False,
                             total_value=0, total_invested=0, total_pnl=0,
                             total_pnl_percent=0, cash_balance=0,
                             holdings_count=0, currency="USD", owner="selvam")
    tv = ti = tc = th = 0.0
    for pk, uk, owner in accounts:
        direct, _, mirrors, credit = _fetch_account(pk, uk, owner)
        for h in direct: tv += h.current_value; ti += h.invested_value
        th += len(direct); tc += credit
        for m in mirrors:
            deposited = float(m.get("depositSummary") or 0)
            available = float(m.get("availableAmount") or 0)
            pv = 0.0
            for p in m.get("positions",[]):
                pobj     = p.get("unrealizedPnL") or {}
                exposure = float(pobj.get("exposureInAccountCurrency") or 0)
                if exposure: pv += exposure
                else:
                    cost = float(p.get("initialAmountInDollars") or p.get("amount") or 0)
                    pv += cost + float(pobj.get("pnL") or 0)
            tv += pv + available; ti += deposited; th += len(m.get("positions",[]))
    owners = [a[2] for a in accounts]
    owner_tag = owners[0] if len(owners) == 1 else "both"
    total_pnl = tv - ti
    return BrokerSummary(
        broker=BrokerName.ETORO, connected=True,
        total_value=round(tv, 2), total_invested=round(ti, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round((total_pnl/ti*100) if ti else 0, 2),
        cash_balance=round(tc, 2), holdings_count=int(th),
        currency="USD", owner=owner_tag,
    )
