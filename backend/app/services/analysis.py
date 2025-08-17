import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app import crud
from datetime import date, timedelta

# --- 核心邏輯重構 ---

def get_returns_dataframe(db: Session, ticker: str):
    """
    一個更通用的輔助函式，用於獲取一支股票 *所有* 歷史數據的回報率 DataFrame。
    我們不再在這裡限制日期。
    """
    daily_data = crud.get_stock_daily_data(db, ticker=ticker)
    if not daily_data:
        return None

    df = pd.DataFrame([vars(d) for d in daily_data])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df['adj_close'] = pd.to_numeric(df['adj_close'])
    
    daily_returns = df['adj_close'].pct_change().dropna()
    return daily_returns.rename(ticker)

def calculate_beta_from_returns(stock_returns: pd.Series, market_returns: pd.Series):
    """
    一個純計算函式，根據傳入的回報率序列計算 Beta。
    """
    if stock_returns is None or market_returns is None or stock_returns.empty or market_returns.empty:
        return None

    combined_df = pd.concat([stock_returns, market_returns], axis=1).dropna()

    # 至少需要 30 個共同交易日才能進行有意義的計算
    if len(combined_df) < 30:
        return None

    covariance_matrix = combined_df.cov()
    covariance = covariance_matrix.iloc[0, 1]
    market_variance = covariance_matrix.iloc[1, 1]
    
    if market_variance == 0:
        return None

    beta = covariance / market_variance
    return beta


def calculate_and_store_analytics(db: Session, ticker: str, years: int = 3):
    """
    計算一支股票的所有核心分析指標 (穩健版)。
    """
    # 1. 獲取 *所有* 可用的歷史回報率
    stock_returns_full = get_returns_dataframe(db, ticker)
    market_returns_full = get_returns_dataframe(db, 'SPY') # 市場基準

    # 2. 檢查是否有足夠的數據進行任何計算
    min_days_required = 252 # 設定最小數據門檻為 1 年
    if stock_returns_full is None or len(stock_returns_full) < min_days_required:
        return {"error": f"Not enough data for {ticker}. Minimum {min_days_required} days required."}
    if market_returns_full is None:
        return {"error": "Market data (SPY) not available for calculation."}

    # 3. 實現靈活的數據窗口邏輯
    start_date = date.today() - timedelta(days=years * 365)
    
    # 嘗試截取指定時間範圍的數據
    stock_returns_period = stock_returns_full.loc[start_date:]
    market_returns_period = market_returns_full.loc[start_date:]
    
    # 檢查截取後的數據是否仍然有效
    if len(stock_returns_period) < 30:
        # 如果截取後數據太少，則回退使用全部數據
        actual_period_days = len(stock_returns_full)
        stock_returns_to_use = stock_returns_full
        market_returns_to_use = market_returns_full
    else:
        # 否則，使用截取後的數據
        actual_period_days = len(stock_returns_period)
        stock_returns_to_use = stock_returns_period
        market_returns_to_use = market_returns_period

    # 4. 使用最終確定的數據集進行計算
    annualized_return = stock_returns_to_use.mean() * 252
    annualized_volatility = stock_returns_to_use.std() * np.sqrt(252)
    beta = calculate_beta_from_returns(stock_returns_to_use, market_returns_to_use)

    # 5. 準備 Pydantic Schema 物件並儲存
    from app.schemas.analytics import AnalyticsCreate
    analytics_data = AnalyticsCreate(
        ticker=ticker,
        analysis_date=date.today(),
        beta=beta,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
    )
    
    db_analytics_result = crud.create_or_update_analytics(db, analytics_data)
    
    # 可以在回傳結果中加入更多元數據
    result_with_metadata = db_analytics_result.__dict__
    result_with_metadata.update({
        "calculation_period_days": actual_period_days,
        "calculation_period_years": round(actual_period_days / 252, 2)
    })
    
    return result_with_metadata