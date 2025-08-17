from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analysis as analysis_service
from app.schemas.analytics import Analytics as AnalyticsSchema # <--- 匯入新的 Schema

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
)

# --- 將 GET 改為 POST，並更新 response_model ---
@router.post("/{ticker}/calculate", response_model=AnalyticsSchema)
def run_and_store_analysis(ticker: str, db: Session = Depends(get_db)):
    """
    觸發對指定股票的分析計算，並將結果儲存到資料庫。
    """
    # 呼叫我們的服務層來執行計算和儲存
    analytics_result = analysis_service.calculate_and_store_analytics(db, ticker=ticker)
    
    if "error" in analytics_result:
        raise HTTPException(status_code=400, detail=analytics_result["error"])
        
    if not analytics_result:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not process analysis for ticker {ticker}. Ensure historical data exists."
        )

    return analytics_result