# InvestOS — Consolidated Investment Dashboard

A full-stack web app that aggregates your portfolio across:
- **Zerodha** (Kite Connect API)
- **Interactive Brokers** (Client Portal API)
- **Sharekhan** (TradeSmart API)
- **eToro** (CSV import)
- **Aionion Capital** (CSV import)

---

## Project Structure

```
investment-dashboard/
├── backend/                    # FastAPI Python backend
│   ├── main.py                 # App entrypoint
│   ├── requirements.txt
│   ├── .env.example            # Copy to .env and fill in your keys
│   ├── models/
│   │   └── schemas.py          # Pydantic data models
│   ├── services/
│   │   ├── zerodha_service.py      # Kite Connect integration
│   │   ├── ibkr_service.py         # IBKR Client Portal integration
│   │   ├── sharekhan_service.py    # TradeSmart integration
│   │   ├── etoro_service.py        # eToro CSV import
│   │   ├── aionion_service.py      # Aionion CSV import
│   │   └── portfolio_service.py    # Aggregation logic
│   └── routers/
│       ├── portfolio.py
│       ├── zerodha.py
│       ├── interactive_brokers.py
│       ├── sharekhan.py
│       ├── etoro.py
│       └── aionion.py
│
├── frontend/                   # React + Recharts frontend
│   ├── src/App.jsx             # Main dashboard UI
│   ├── vite.config.js
│   └── package.json
│
├── docker-compose.yml          # Run everything with one command
└── README.md
```

---

## Quick Start (Local Dev)

### 1. Backend

```bash
cd backend
cp .env.example .env       # Fill in your API keys
pip install -r requirements.txt
uvicorn main:app --reload
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Dashboard running at http://localhost:3000
```

### 3. Docker (Full Stack)

```bash
docker-compose up --build
# Dashboard: http://localhost:3000
# API:       http://localhost:8000
```

---

## Broker Setup Guide

### Zerodha (Kite Connect)
1. Register at https://developers.kite.trade/
2. Create an app → get `api_key` and `api_secret`
3. Generate an access token daily via login flow:
   ```
   GET https://kite.trade/connect/login?api_key=xxx&v=3
   ```
4. Set `ZERODHA_API_KEY` and `ZERODHA_ACCESS_TOKEN` in `.env`
5. Uncomment `kiteconnect` lines in `zerodha_service.py`
6. Install: `pip install kiteconnect`

### Interactive Brokers
1. Download IBKR Client Portal Gateway from:
   https://www.interactivebrokers.com/en/trading/ib-api.php
2. Run gateway locally: `./bin/run.sh root/conf.yaml`
3. Login at `https://localhost:5000`
4. Set `IBKR_ACCOUNT_ID` in `.env`
5. Uncomment the `_get()` calls in `ibkr_service.py`

### Sharekhan
1. Apply for API access at https://developers.sharekhan.com/
2. Set `SHAREKHAN_USER_ID`, `SHAREKHAN_PASSWORD`, `SHAREKHAN_API_KEY`
3. Uncomment API calls in `sharekhan_service.py`

### eToro (CSV Import)
1. Login to eToro → Portfolio → click Download icon
2. Export "Account Statement"
3. Place CSV at `backend/data/etoro_portfolio.csv`
   OR upload via: `POST /api/etoro/upload`

### Aionion Capital (CSV Import)
1. Download portfolio statement from Aionion account
2. Place CSV at `backend/data/aionion_portfolio.csv`
   OR upload via: `POST /api/aionion/upload`

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/summary` | Consolidated portfolio summary |
| GET | `/api/portfolio/holdings` | All holdings across all brokers |
| GET | `/api/portfolio/performance` | 30-day performance history |
| GET | `/api/portfolio/allocation/broker` | Allocation by broker |
| GET | `/api/portfolio/allocation/asset` | Allocation by asset type |
| GET | `/api/zerodha/holdings` | Zerodha holdings only |
| GET | `/api/ibkr/holdings` | IBKR holdings only |
| GET | `/api/sharekhan/holdings` | Sharekhan holdings only |
| POST | `/api/etoro/upload` | Upload eToro CSV |
| POST | `/api/aionion/upload` | Upload Aionion Capital CSV |

Full interactive docs: `http://localhost:8000/docs`

---

## Next Steps / Roadmap

- [ ] PostgreSQL integration for historical tracking
- [ ] Redis caching to reduce API calls
- [ ] Daily P&L tracking with charts
- [ ] Price alerts and notifications (email/Telegram)
- [ ] Auto-refresh with WebSocket
- [ ] Mobile-responsive layout
- [ ] Export portfolio to Excel/PDF
- [ ] Currency conversion (USD ↔ INR) via live FX rates
