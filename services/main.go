package main

import (
	"context"
	"log"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/piquette/finance-go/chart"
	"github.com/piquette/finance-go/quote"
)

// 資料庫連接字串
const DATABASE_URL = "postgresql://quantuser:quantpassword@localhost:5434/quantdb"

// main 函式是程式的入口
func main() {
	log.Println("開始執行數據獲取服務...")

	// 1. 連接到資料庫
	dbpool, err := pgxpool.New(context.Background(), DATABASE_URL)
	if err != nil {
		log.Fatalf("無法連接到資料庫: %v\n", err)
	}
	// defer 確保在 main 函式結束時，資料庫連接池會被關閉
	defer dbpool.Close()

	log.Println("資料庫連接成功！")

	// 2. 定義我們要獲取的股票列表
	tickers := []string{"AAPL", "MSFT", "GOOGL"}

	// 3. 遍歷列表，逐一處理每支股票
	for _, ticker := range tickers {
		processTicker(ticker, dbpool)
	}

	log.Println("數據獲取服務執行完畢！")
}

// processTicker 處理單一股票的數據獲取與儲存
func processTicker(ticker string, dbpool *pgxpool.Pool) {
	log.Printf("正在處理: %s\n", ticker)

	// 4. 從 yfinance 獲取股票基本資訊
	q, err := quote.Get(ticker)
	if err != nil {
		log.Printf("錯誤: 無法獲取 %s 的基本資訊: %v\n", ticker, err)
		return
	}

	// 準備要寫入 'stocks' 表的數據
	stockName := q.ShortName
	exchange := q.FullExchangeName
	sharesOutstanding := q.SharesOutstanding

	// 5. 將股票基本資訊存入 'stocks' 資料表 (如果不存在)
	// ON CONFLICT DO NOTHING 是一個很方便的語法，如果 ticker 已存在，就什麼都不做
	insertStockSQL := `
		INSERT INTO stocks (ticker, stock_name, exchange, shares_outstanding, is_active)
		VALUES ($1, $2, $3, $4, true)
		ON CONFLICT (ticker) DO NOTHING;
	`
	_, err = dbpool.Exec(context.Background(), insertStockSQL, ticker, stockName, exchange, sharesOutstanding)
	if err != nil {
		log.Printf("錯誤: 無法將 %s 寫入 stocks 表: %v\n", ticker, err)
		return
	}

	// 6. 獲取過去 10 年的歷史日K線數據
	p := &chart.Params{
		Symbol:   ticker,
		Start:    chart.Date(time.Now().Year()-10, int(time.Now().Month()), time.Now().Day()),
		End:      chart.Date(time.Now().Year(), int(time.Now().Month()), time.Now().Day()),
		Interval: chart.IntervalDaily,
	}
	iter := chart.Get(p)

	// 7. 遍歷歷史數據並寫入 'stock_daily_data' 表
	for iter.Next() {
		bar := iter.Bar()
		insertDailySQL := `
			INSERT INTO stock_daily_data (ticker, date, open, high, low, close, adj_close, volume)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
			ON CONFLICT (ticker, date) DO NOTHING; 
		`
		// time.Unix 將 yfinance 回傳的時間戳轉換為 Go 的時間格式
		date := time.Unix(int64(bar.Timestamp), 0)

		_, err := dbpool.Exec(context.Background(), insertDailySQL, ticker, date, bar.Open, bar.High, bar.Low, bar.Close, bar.AdjClose, bar.Volume)
		if err != nil {
			log.Printf("錯誤: 無法寫入 %s 在 %s 的日K數據: %v\n", ticker, date.Format("2006-01-02"), err)
		}
	}

	if err := iter.Err(); err != nil {
		log.Printf("錯誤: 遍歷 %s 的歷史數據時出錯: %v\n", ticker, err)
	}

	log.Printf("%s 處理完畢。\n", ticker)
}

// 為了讓 Go 專案能正確下載 yfinance 的函式庫，我們需要安裝它
func init() {
	// 這是一個小技巧，Go 會在編譯時自動下載這裡 import 的套件
	_ = quote.Get
}
