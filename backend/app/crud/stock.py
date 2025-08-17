from sqlalchemy.orm import Session
# 👇 確保 StockDailyDataModel 也被匯入了
from ..models.stock import Stock as StockModel, StockDailyData as StockDailyDataModel
from ..schemas.stock import StockCreate

def get_stock(db: Session, ticker: str):
    """
    根據 ticker 查詢單一股票。
    """
    # .first() 會回傳第一個匹配的結果，如果沒有則回傳 None
    return db.query(StockModel).filter(StockModel.ticker == ticker).first()

def get_stocks(db: Session, skip: int = 0, limit: int = 100):
    """
    查詢股票列表，支援分頁。
    - skip: 跳過前 N 筆資料
    - limit: 最多回傳 N 筆資料
    """
    return db.query(StockModel).offset(skip).limit(limit).all()

def create_stock(db: Session, stock: StockCreate):
    """
    新增一筆股票資料。
    """
    db_stock = StockModel(**stock.model_dump())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def get_stock_daily_data(db: Session, ticker: str, start_date: str | None = None, end_date: str | None = None):
    """
    查詢一支股票的所有歷史日 K 線數據，可選日期範圍。
    """
    # 建立一個基礎查詢，指定要查詢的模型和過濾條件
    query = db.query(StockDailyDataModel).filter(StockDailyDataModel.ticker == ticker)
    
    # 如果提供了開始日期，則加入日期過濾條件
    if start_date:
        query = query.filter(StockDailyDataModel.date >= start_date)
    if end_date:
        query = query.filter(StockDailyDataModel.date <= end_date)
        
    # 按照日期升序排列並回傳所有結果
    return query.order_by(StockDailyDataModel.date.asc()).all()