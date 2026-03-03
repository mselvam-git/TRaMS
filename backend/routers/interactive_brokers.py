from fastapi import APIRouter
from services import ibkr_service

router = APIRouter()

@router.get("/holdings")
def get_holdings():
    return ibkr_service.fetch_holdings()

@router.get("/summary")
def get_summary():
    return ibkr_service.fetch_summary()
