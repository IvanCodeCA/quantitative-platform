from sqlalchemy.orm import Session
from ..models.analytics import StockAnalytics as AnalyticsModel
from ..schemas.analytics import AnalyticsCreate

def create_or_update_analytics(db: Session, analytics_data: AnalyticsCreate):
    """
    新增或更新一筆股票的分析數據。
    如果指定 ticker 和 date 的紀錄已存在，則更新它；否則，新增一筆。
    """
    # 將 Pydantic Schema 轉換為字典
    data_dict = analytics_data.model_dump()
    
    # 使用 merge() 方法，這是一個非常方便的 "upsert" (update or insert) 操作
    # 它會根據主鍵自動判斷是該新增還是更新
    db_analytics = db.merge(AnalyticsModel(**data_dict))
    
    db.commit()
    db.refresh(db_analytics)
    return db_analytics