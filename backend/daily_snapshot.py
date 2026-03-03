#!/usr/bin/env python3
"""
TRaMS Daily Snapshot Script
============================
Saves portfolio + holdings + bonds + FX to PostgreSQL.
Run daily via cron:
  0 20 * * 1-5  /Users/selvam/Downloads/investment-dashboard/backend/venv/bin/python3 \
                /Users/selvam/Downloads/investment-dashboard/backend/daily_snapshot.py

Or manually:
  source venv/bin/activate && python3 daily_snapshot.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(".env", override=True)

print("=" * 55)
print("TRaMS Daily Snapshot")
print("=" * 55)

from services import (
    zerodha_service, ibkr_service, sharekhan_service,
    etoro_service, aionion_service, db_service
)

# ── 1. Fetch live FX rates ────────────────────────────────────────
try:
    import requests
    r = requests.get("https://api.exchangerate.host/latest?base=INR&symbols=USD,EUR", timeout=8)
    if r.status_code == 200:
        rates = r.json().get("rates", {})
        usd_inr = round(1 / rates["USD"], 2) if "USD" in rates else 83.5
        eur_inr = round(1 / rates["EUR"], 2) if "EUR" in rates else 90.2
    else:
        usd_inr, eur_inr = 83.5, 90.2
except Exception as e:
    print(f"  FX fetch failed ({e}), using defaults")
    usd_inr, eur_inr = 83.5, 90.2

db_service.update_fx_rates(usd_inr, eur_inr)
print(f"  FX: 1 USD = ₹{usd_inr}  |  1 EUR = ₹{eur_inr}")

FX_TO_INR = {"INR": 1.0, "USD": usd_inr, "EUR": eur_inr}

def to_inr(amount, currency):
    return amount * FX_TO_INR.get(currency, 1.0)

# ── 2. Fetch all holdings ─────────────────────────────────────────
print("\nFetching holdings...")
all_holdings = []
for name, svc in [
    ("Zerodha",    zerodha_service),
    ("Sharekhan",  sharekhan_service),
    ("IBKR",       ibkr_service),
    ("eToro",      etoro_service),
    ("Aionion",    aionion_service),
]:
    try:
        h = svc.fetch_holdings()
        all_holdings.extend(h)
        print(f"  {name}: {len(h)} holdings")
    except Exception as e:
        print(f"  {name}: ERROR — {e}")

db_service.save_holdings_snapshot(all_holdings)
print(f"  Saved {len(all_holdings)} holdings to DB")

# ── 3. Fetch bonds ────────────────────────────────────────────────
print("\nFetching bonds...")
try:
    bonds = aionion_service.fetch_bonds()
    db_service.save_bonds_snapshot(bonds)
    print(f"  Aionion bonds: {len(bonds)}")
except Exception as e:
    print(f"  Bonds ERROR: {e}")
    bonds = []

# ── 4. Compute owner-wise values & save snapshots ─────────────────
print("\nComputing portfolio values...")

selvam_brokers  = {"Zerodha", "Sharekhan"}
radhika_brokers = {"Aionion Capital"}

selvam_val  = 0.0
radhika_val = 0.0
combined_invested = 0.0

for svc, broker_name in [
    (zerodha_service,   "Zerodha"),
    (sharekhan_service, "Sharekhan"),
    (ibkr_service,      "Interactive Brokers"),
    (etoro_service,     "eToro"),
    (aionion_service,   "Aionion Capital"),
]:
    try:
        s = svc.fetch_summary()
        val_inr = to_inr(s.total_value, s.currency)
        pnl_inr = to_inr(s.total_pnl, s.currency)
        inv_inr = to_inr(s.total_invested, s.currency)
        combined_invested += inv_inr

        owner = s.owner or ("selvam" if broker_name in selvam_brokers else "radhika")
        db_service.save_portfolio_snapshot(owner, broker_name, val_inr, inv_inr, pnl_inr, "INR", usd_inr, eur_inr)
        print(f"  {broker_name}: ₹{val_inr:,.0f} (P&L: ₹{pnl_inr:,.0f})")
    except Exception as e:
        print(f"  {broker_name}: ERROR — {e}")

# For IBKR and eToro split by holding.owner
for h in all_holdings:
    if h.broker.value in ("Interactive Brokers", "eToro"):
        v = to_inr(h.current_value, h.currency)
        if h.owner == "selvam":
            selvam_val += v
        else:
            radhika_val += v

# Add Indian brokers
selvam_val  += sum(to_inr(h.current_value, h.currency) for h in all_holdings if h.broker.value in selvam_brokers)
radhika_val += sum(to_inr(h.current_value, h.currency) for h in all_holdings if h.broker.value in radhika_brokers)
radhika_val += sum(b.principal_amount for b in bonds)

combined_val = selvam_val + radhika_val
combined_pnl = combined_val - combined_invested

db_service.save_portfolio_snapshot("selvam",   None, selvam_val,   0, 0, "INR", usd_inr, eur_inr)
db_service.save_portfolio_snapshot("radhika",  None, radhika_val,  0, 0, "INR", usd_inr, eur_inr)
db_service.save_portfolio_snapshot("combined", None, combined_val, combined_invested, combined_pnl, "INR", usd_inr, eur_inr)

print(f"\n  Selvam:   ₹{selvam_val:,.0f}")
print(f"  Radhika:  ₹{radhika_val:,.0f}")
print(f"  Combined: ₹{combined_val:,.0f} (P&L: ₹{combined_pnl:,.0f})")
print("\n✅ Snapshot saved to PostgreSQL")
