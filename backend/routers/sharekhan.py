from fastapi import APIRouter
from services import sharekhan_service

router = APIRouter()

@router.get("/holdings")
def get_holdings():
    return sharekhan_service.fetch_holdings()

@router.get("/summary")
def get_summary():
    return sharekhan_service.fetch_summary()
