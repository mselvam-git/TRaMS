from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import zerodha, interactive_brokers, sharekhan, etoro, aionion, portfolio

app = FastAPI(title="TRaMS Portfolio API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Allow file:// and any localhost port
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zerodha.router,            prefix="/api/zerodha",   tags=["Zerodha"])
app.include_router(interactive_brokers.router, prefix="/api/ibkr",      tags=["IBKR"])
app.include_router(sharekhan.router,           prefix="/api/sharekhan", tags=["Sharekhan"])
app.include_router(etoro.router,               prefix="/api/etoro",     tags=["eToro"])
app.include_router(aionion.router,             prefix="/api/aionion",   tags=["Aionion"])
app.include_router(portfolio.router,           prefix="/api/portfolio", tags=["Portfolio"])

@app.get("/")
def root():
    return {"status": "TRaMS API v2.0 running", "docs": "/docs"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/status")
def broker_status():
    """Quick connectivity check for all brokers — used by the dashboard topbar."""
    import os
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path, override=True)
    return {
        "zerodha":   bool(os.getenv("ZERODHA_API_KEY") and os.getenv("ZERODHA_ACCESS_TOKEN")),
        "sharekhan": bool(os.getenv("SHAREKHAN_API_KEY") and os.getenv("SHAREKHAN_ACCESS_TOKEN")),
        "etoro_selvam":  bool(os.getenv("ETORO_PUBLIC_KEY") and os.getenv("ETORO_USER_KEY")),
        "etoro_radhika": bool(os.getenv("ETORO_RADHIKA_PUBLIC_KEY") and os.getenv("ETORO_RADHIKA_USER_KEY")),
        "aionion":   bool(os.getenv("AIONION_TOKEN") and os.getenv("AIONION_USER_ID")),
        "ibkr":      bool(os.getenv("IBKR_GATEWAY_URL")),
    }
