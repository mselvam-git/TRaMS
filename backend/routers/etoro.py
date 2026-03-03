from fastapi import APIRouter
from services import etoro_service

router = APIRouter()

@router.get("/holdings")
def get_holdings():
    return etoro_service.fetch_holdings()

@router.get("/holdings/direct")
def get_direct_holdings():
    return etoro_service.fetch_holdings(include_copy=False)

@router.get("/copy-traders")
def get_copy_traders():
    return etoro_service.fetch_copy_trader_summary()

@router.get("/performance")
def get_performance(owner: str = None):
    return etoro_service.fetch_performance_history(owner)

@router.get("/profiles")
def get_profiles():
    return etoro_service.fetch_user_profiles()

@router.get("/summary")
def get_summary():
    return etoro_service.fetch_summary()
