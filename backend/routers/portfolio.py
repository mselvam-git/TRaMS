from fastapi import APIRouter
from services import portfolio_service

router = APIRouter()

@router.get("/summary")
def get_portfolio_summary():
    return portfolio_service.get_portfolio_summary()

@router.get("/holdings")
def get_all_holdings():
    return portfolio_service.get_all_holdings()

@router.get("/performance")
def get_performance():
    return portfolio_service.get_performance_history()

@router.get("/allocation/sector")
def get_sector_allocation():
    holdings = portfolio_service.get_all_holdings()
    return portfolio_service.get_sector_allocation(holdings)

@router.get("/allocation/asset")
def get_asset_allocation():
    holdings = portfolio_service.get_all_holdings()
    return portfolio_service.get_asset_allocation(holdings)

@router.get("/allocation/broker")
def get_broker_allocation():
    summary = portfolio_service.get_portfolio_summary()
    return portfolio_service.get_broker_allocation(summary.brokers)
