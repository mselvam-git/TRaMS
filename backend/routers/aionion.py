from fastapi import APIRouter, UploadFile, File
from services import aionion_service

router = APIRouter()

@router.get("/holdings")
def get_holdings():
    return aionion_service.fetch_holdings_from_csv()

@router.get("/summary")
def get_summary():
    return aionion_service.fetch_summary()

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload Aionion Capital portfolio CSV export."""
    content = await file.read()
    holdings = aionion_service.fetch_holdings_from_csv(content.decode("utf-8"))
    return {"uploaded": len(holdings), "holdings": holdings}
