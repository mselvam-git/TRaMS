"""Portfolio Aggregation Service — combines all brokers concurrently."""
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict
from models.schemas import Holding, BrokerSummary, PortfolioSummary, BrokerName
from services import zerodha_service, ibkr_service, sharekhan_service, etoro_service, aionion_service

FX_USD_INR = 83.5
FX_EUR_INR = 90.2

def _to_inr(val: float, currency: str) -> float:
    if currency == "USD": return val * FX_USD_INR
    if currency == "EUR": return val * FX_EUR_INR
    return val

# Per-broker timeout in seconds (IBKR returns from cache instantly now)
_BROKER_TIMEOUT = 30

def get_all_holdings() -> List[Holding]:
    tasks = {
        "zerodha":   zerodha_service.fetch_holdings,
        "ibkr":      ibkr_service.fetch_holdings,
        "sharekhan": sharekhan_service.fetch_holdings,
        "etoro":     etoro_service.fetch_holdings,
        "aionion":   aionion_service.fetch_holdings_from_csv,
    }
    all_holdings: List[Holding] = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures, timeout=_BROKER_TIMEOUT + 5):
            name = futures[future]
            try:
                result = future.result(timeout=_BROKER_TIMEOUT)
                all_holdings.extend(result)
            except TimeoutError:
                print(f"[Portfolio] {name} timed out — skipping")
            except Exception as e:
                print(f"[Portfolio] {name} error: {e}")
    return all_holdings

def get_portfolio_summary() -> PortfolioSummary:
    broker_fns = {
        "zerodha":   zerodha_service.fetch_summary,
        "ibkr":      ibkr_service.fetch_summary,
        "sharekhan": sharekhan_service.fetch_summary,
        "etoro":     etoro_service.fetch_summary,
        "aionion":   aionion_service.fetch_summary,
    }
    broker_summaries: List[BrokerSummary] = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fn): name for name, fn in broker_fns.items()}
        for future in as_completed(futures, timeout=_BROKER_TIMEOUT + 5):
            name = futures[future]
            try:
                s = future.result(timeout=_BROKER_TIMEOUT)
                broker_summaries.append(s)
            except TimeoutError:
                print(f"[Portfolio] {name} summary timed out — skipping")
            except Exception as e:
                print(f"[Portfolio] {name} summary error: {e}")

    # Sort into consistent display order
    _order = ["Zerodha", "Interactive Brokers", "Sharekhan", "eToro", "Aionion Capital"]
    broker_summaries.sort(key=lambda b: _order.index(b.broker) if b.broker in _order else 99)

    total_value    = sum(_to_inr(b.total_value,    b.currency) for b in broker_summaries)
    total_invested = sum(_to_inr(b.total_invested, b.currency) for b in broker_summaries)
    total_pnl      = total_value - total_invested
    total_holdings = sum(b.holdings_count for b in broker_summaries)

    selvam_val  = 0.0
    radhika_val = 0.0
    for b in broker_summaries:
        v = _to_inr(b.total_value, b.currency)
        if b.owner == "radhika":
            radhika_val += v
        elif b.owner == "selvam":
            selvam_val += v
        else:
            # "both" — eToro has mixed accounts; split evenly
            selvam_val  += v * 0.5
            radhika_val += v * 0.5

    return PortfolioSummary(
        total_value=round(total_value, 2),
        total_invested=round(total_invested, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_percent=round((total_pnl / total_invested * 100) if total_invested else 0, 2),
        day_pnl=0.0,
        day_pnl_percent=0.0,
        brokers=broker_summaries,
        total_holdings=total_holdings,
        selvam_value=round(selvam_val,  2),
        radhika_value=round(radhika_val, 2),
    )

def get_sector_allocation(holdings: List[Holding]) -> List[Dict]:
    sectors: Dict[str, float] = {}
    total = sum(_to_inr(h.current_value, h.currency) for h in holdings)
    for h in holdings:
        s = h.sector or "Unclassified"
        sectors[s] = sectors.get(s, 0) + _to_inr(h.current_value, h.currency)
    return [{"sector": s, "value": round(v,2), "percent": round(v/total*100,2) if total else 0}
            for s, v in sorted(sectors.items(), key=lambda x: -x[1])]

def get_asset_allocation(holdings: List[Holding]) -> List[Dict]:
    assets: Dict[str, float] = {}
    total = sum(_to_inr(h.current_value, h.currency) for h in holdings)
    for h in holdings:
        k = h.asset_type.value.replace("_"," ").title()
        assets[k] = assets.get(k, 0) + _to_inr(h.current_value, h.currency)
    return [{"type": k, "value": round(v,2), "percent": round(v/total*100,2) if total else 0}
            for k, v in sorted(assets.items(), key=lambda x: -x[1])]

def get_broker_allocation(summaries: List[BrokerSummary]) -> List[Dict]:
    total = sum(_to_inr(b.total_value, b.currency) for b in summaries)
    return [{"broker": b.broker.value,
             "value": round(_to_inr(b.total_value, b.currency), 2),
             "percent": round(_to_inr(b.total_value, b.currency)/total*100, 2) if total else 0}
            for b in summaries]

def get_performance_history():
    try:
        return etoro_service.fetch_performance_history()
    except Exception as e:
        print(f"[Portfolio] Performance error: {e}")
        return {}
