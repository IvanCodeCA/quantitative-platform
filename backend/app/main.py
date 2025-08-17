from fastapi import FastAPI
from app.api import stocks, analysis

# 建立 FastAPI 應用程式實例
app = FastAPI(
    title="AI-Powered Quantitative Trading & Analysis Platform API",
    version="1.0.0"
)

# 將 stocks router 掛載到主應用程式上
app.include_router(stocks.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")

# 根路徑，用於快速測試伺服器是否正常運行
@app.get("/")
def read_root():
    return {"message": "Welcome to the Quant Platform API!"}