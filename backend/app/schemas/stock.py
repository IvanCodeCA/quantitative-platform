from pydantic import BaseModel, ConfigDict

# --- 用於從 API 回應中讀取數據的 Schema ---
class StockBase(BaseModel):
    ticker: str
    stock_name: str
    exchange: str | None = None # | None 表示這個欄位是可選的
    industry: str | None = None
    shares_outstanding: int | None = None # 允許這個欄位在新增時為空
    is_active: bool = True

    # Pydantic V2 的新設定，允許從 ORM 模型直接轉換
    model_config = ConfigDict(from_attributes=True)

# --- 用於透過 API 新增數據的 Schema ---
class StockCreate(StockBase):
    pass # 目前與 StockBase 相同，但未來可能會有不同

# --- 用於從資料庫讀取並透過 API 回傳的 Schema ---
class Stock(StockBase):
    # 這個 Schema 包含了所有 StockBase 的欄位
    # 如果未來有不想回傳給使用者的欄位，可以在這裡排除
    pass