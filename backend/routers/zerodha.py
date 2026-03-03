from fastapi import APIRouter
from services import zerodha_service

router = APIRouter()

@router.get("/holdings")
def get_holdings():
    return zerodha_service.fetch_holdings()

@router.get("/summary")
def get_summary():
    return zerodha_service.fetch_summary()
