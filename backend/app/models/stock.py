import datetime
from sqlalchemy import String, Date, Boolean, BigInteger, Numeric
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

# 這是所有模型都會繼承的基礎類別
# 它可以幫助 SQLAlchemy 管理我們的資料表
class Base(DeclarativeBase):
    pass

class Stock(Base):
    __tablename__ = "stocks"

    # 定義 'stocks' 資料表的欄位
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    stock_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    shares_outstanding: Mapped[int] = mapped_column(BigInteger, nullable=True) 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StockDailyData(Base):
    __tablename__ = "stock_daily_data"

    # 定義 'stock_daily_data' 資料表的欄位
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    adj_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)