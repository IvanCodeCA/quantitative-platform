from pydantic import BaseModel, ConfigDict
from datetime import date

# --- 用於透過 API 新增或更新分析數據的 Schema ---
class AnalyticsCreate(BaseModel):
    ticker: str
    analysis_date: date
    beta: float | None = None
    annualized_return: float | None = None
    annualized_volatility: float | None = None

# --- 用於從資料庫讀取並透過 API 回傳的 Schema ---
class Analytics(AnalyticsCreate):
    # 這個設定允許 Pydantic 從 SQLAlchemy 的 ORM 模型直接轉換
    model_config = ConfigDict(from_attributes=True)