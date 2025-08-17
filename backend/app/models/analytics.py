from sqlalchemy import String, Date, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date

from .stock import Base # 從 stock.py 匯入我們共用的 Base

class StockAnalytics(Base):
    __tablename__ = "stock_analytics"

    ticker: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.ticker"), primary_key=True)
    # 分析的計算日期，代表這個數據是基於到哪一天的歷史數據算出來的
    analysis_date: Mapped[date] = mapped_column(Date, primary_key=True)

    # 分析指標欄位
    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    annualized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    annualized_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # 可以在此處加入更多未來的分析指標，例如 Sharpe Ratio, Alpha 等