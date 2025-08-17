from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- 資料庫連接設定 ---
# 格式: "postgresql://使用者名稱:密碼@主機:port/資料庫名稱"
DATABASE_URL = "postgresql://quantuser:quantpassword@localhost:5434/quantdb"

# 建立資料庫引擎 (Engine)
# 'echo=True' 會在終端機中顯示 SQLAlchemy 產生的 SQL 語句，對於除錯非常有用
engine = create_engine(DATABASE_URL, echo=True)

# 建立一個 SessionLocal 類別，它將作為我們資料庫會話的工廠
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 取得資料庫會話的依賴項 (Dependency)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()