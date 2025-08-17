from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List # <--- 新增 List 的匯入

# 更新匯入路徑，改為匯入我們新的 crud 模組
from app import crud
from app.database import get_db
from app.models.stock import Stock as StockModel
from app.schemas.stock import Stock as StockSchema, StockCreate

# 建立一個 APIRouter 實例
router = APIRouter(
    prefix="/stocks",  # 所有這個 router 裡的 API 路徑都會以 /stocks 開頭
    tags=["Stocks"],     # 在 API 文件中將它們分組到 "Stocks" 標籤下
)

# --- 更新 POST 端點，改為呼叫 CRUD 函式 ---
@router.post("/", response_model=StockSchema, status_code=201)
def create_stock_endpoint(stock: StockCreate, db: Session = Depends(get_db)):
    """
    新增一筆新的股票到資料庫中。
    """
    # 檢查股票是否已存在
    db_stock = crud.get_stock(db, ticker=stock.ticker)
    if db_stock:
        raise HTTPException(status_code=409, detail="Stock with this ticker already exists.")
    
    # 呼叫 CRUD 函式來新增股票
    return crud.create_stock(db=db, stock=stock)

# --- API 端點：新增一筆股票 ---
@router.post("/", response_model=StockSchema, status_code=201)
def create_stock(stock: StockCreate, db: Session = Depends(get_db)):
    """
    新增一筆新的股票到資料庫中。
    - **ticker**: 股票代碼 (必須)
    - **stock_name**: 公司名稱 (必須)
    - **exchange**: 交易所 (可選)
    - **industry**: 產業 (可選)
    """
    # 將傳入的 Pydantic Schema 物件轉換為 SQLAlchemy Model 物件
    db_stock = StockModel(**stock.model_dump())
    
    # 將 Model 物件加入到資料庫會話中
    db.add(db_stock)
    
    try:
        # 提交會話，將變更寫入資料庫
        db.commit()
        # 刷新 db_stock 物件，以獲取資料庫生成的任何新數據 (例如預設值)
        db.refresh(db_stock)
    except IntegrityError:
        # 如果發生 IntegrityError，通常是因為主鍵 (ticker) 重複
        db.rollback() # 回滾事務
        raise HTTPException(status_code=409, detail="Stock with this ticker already exists.")
    
    return db_stock

# --- 新增 GET 端點：查詢所有股票 ---
@router.get("/", response_model=List[StockSchema])
def read_stocks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    讀取股票列表，預設回傳前 100 筆。
    """
    stocks = crud.get_stocks(db, skip=skip, limit=limit)
    return stocks

# --- 新增 GET 端點：查詢單一股票 ---
@router.get("/{ticker}", response_model=StockSchema)
def read_stock(ticker: str, db: Session = Depends(get_db)):
    """
    根據 ticker 讀取單一股票的詳細資訊。
    """
    db_stock = crud.get_stock(db, ticker=ticker)
    if db_stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return db_stock