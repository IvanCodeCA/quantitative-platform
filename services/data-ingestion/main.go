package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	fmp "github.com/spacecodewor/fmpcloud-go"
)

const FMP_API_KEY = "YOUR_FMP_API_KEY"
const DATABASE_URL = "postgresql://quantuser:quantpassword@localhost:5434/quantdb"
const NASDAQ_LIST_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
const OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
const NUM_WORKERS = 6

// Structs to decode the FMP API response
type FmpHistoricalResponse struct {
	Symbol     string   `json:"symbol"`
	Historical []FmpBar `json:"historical"`
}
type FmpBar struct {
	Date     string  `json:"date"`
	Open     float64 `json:"open"`
	High     float64 `json:"high"`
	Low      float64 `json:"low"`
	Close    float64 `json:"close"`
	AdjClose float64 `json:"adjClose"`
	Volume   int64   `json:"volume"`
}

// StockInfo stores data parsed from the exchange .txt files
type StockInfo struct {
	Ticker string
	Name   string
}

func main() {
	// ... (日誌和客戶端設定保持不變) ...
	logFile, _ := os.OpenFile("data-ingestion.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	mw := io.MultiWriter(os.Stdout, logFile)
	log.SetOutput(mw)
	godotenv.Load()
	apiKey := os.Getenv("FMP_API_KEY")
	dbURL := os.Getenv("DATABASE_URL")
	if apiKey == "" || dbURL == "" {
		log.Fatalln("錯誤: FMP_API_KEY 或 DATABASE_URL 未設定。")
	}

	log.Println("----------------------------------------------------")
	log.Println("開始執行數據獲取與股票列表更新服務...")
	fmpClient, _ := fmp.NewAPIClient(fmp.Config{APIKey: apiKey})
	dbpool, _ := pgxpool.New(context.Background(), dbURL)
	defer dbpool.Close()
	log.Println("資料庫連接成功！")

	// ... (清空資料表和建立股票列表的邏輯保持不變) ...
	dbpool.Exec(context.Background(), "TRUNCATE TABLE stock_daily_data;")
	masterList, _ := buildMasterStockList()
	log.Printf("成功獲取最新的股票主列表，共 %d 支股票。", len(masterList))
	deactivateDelistedStocks(masterList, dbpool)
	if _, exists := masterList["SPY"]; !exists {
		log.Println("注意: SPY 不在主列表中，將手動添加以進行 Beta 計算。")
		masterList["SPY"] = StockInfo{Ticker: "SPY", Name: "SPDR S&P 500 ETF Trust"}
	}

	// --- VVVV 修正後的併發邏輯 VVVV ---
	var wg sync.WaitGroup
	totalJobs := len(masterList)
	jobs := make(chan string, totalJobs)
	var processedCounter atomic.Int32

	// 1. 啟動工人。他們會立刻開始等待從 jobs channel 傳來的任務。
	for w := 1; w <= NUM_WORKERS; w++ {
		go worker(w, jobs, &wg, &processedCounter, totalJobs, fmpClient, dbpool, apiKey)
	}

	// 2. 在分配任何任務之前，先告訴 WaitGroup 總共有多少個任務。
	wg.Add(totalJobs)

	// 3. 將所有任務（股票代碼）發送到 jobs channel。
	for _, stock := range masterList {
		jobs <- stock.Ticker
	}
	close(jobs) // 發送完畢後關閉 channel，這樣工人在處理完所有任務後會自動退出。

	// 4. 在這裡等待。因為計數器已經被設定為 totalJobs，所以 main 函式會在這裡
	//    耐心等待，直到所有工人都呼叫了 wg.Done()，計數器變回 0。
	wg.Wait()

	log.Println("所有任務處理完畢！")
	log.Println("數據獲取服務執行完畢！")
}

// worker function for the concurrent pool
func worker(id int, jobs <-chan string, wg *sync.WaitGroup, counter *atomic.Int32, total int, fmp *fmp.APIClient, dbpool *pgxpool.Pool, apiKey string) {
	for ticker := range jobs {
		// 注意：wg.Add(1) 已經被移除了
		processTicker(ticker, fmp, dbpool, apiKey)
		count := counter.Add(1)
		log.Printf("進度: %d/%d (%s 完成)", count, total, ticker)
		// 工人唯一的職責是，在完成自己的任務後，通知經理一聲。
		wg.Done()
	}
}

// buildMasterStockList downloads and merges lists from NASDAQ and NYSE.
func buildMasterStockList() (map[string]StockInfo, error) {
	masterList := make(map[string]StockInfo)

	log.Println("正在下載 NASDAQ 列表...")
	nasdaqStocks, err := parseStockList(NASDAQ_LIST_URL, "|", 0, 1, true)
	if err != nil {
		return nil, fmt.Errorf("解析 NASDAQ 列表失敗: %w", err)
	}
	for _, stock := range nasdaqStocks {
		masterList[stock.Ticker] = stock
	}

	log.Println("正在下載其他交易所列表 (NYSE, AMEX)...")
	otherStocks, err := parseStockList(OTHER_LISTED_URL, "|", 0, 1, true)
	if err != nil {
		return nil, fmt.Errorf("解析其他交易所列表失敗: %w", err)
	}
	for _, stock := range otherStocks {
		masterList[stock.Ticker] = stock
	}

	return masterList, nil
}

// parseStockList is a generic parser for the exchange .txt files.
func parseStockList(url, delimiter string, tickerIndex, nameIndex int, skipHeader bool) ([]StockInfo, error) {
	resp, err := http.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var stocks []StockInfo
	scanner := bufio.NewScanner(resp.Body)

	if skipHeader && scanner.Scan() {
		// Skip header line
	}

	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "File Creation Date") {
			continue
		}

		parts := strings.Split(line, delimiter)
		if len(parts) > tickerIndex && len(parts) > nameIndex {
			ticker := parts[tickerIndex]
			name := parts[nameIndex]

			// Filter out test symbols and other noise
			if strings.Contains(ticker, "$") || strings.Contains(ticker, ".") {
				continue
			}

			stocks = append(stocks, StockInfo{Ticker: ticker, Name: name})
		}
	}
	return stocks, scanner.Err()
}

// deactivateDelistedStocks finds stocks in our DB that are no longer in the master list and marks them inactive.
func deactivateDelistedStocks(masterList map[string]StockInfo, dbpool *pgxpool.Pool) {
	log.Println("正在檢查並處理已下市的股票...")

	query := "SELECT ticker FROM stocks WHERE is_active = true"
	rows, err := dbpool.Query(context.Background(), query)
	if err != nil {
		log.Printf("錯誤: 無法從資料庫查詢活躍股票: %v", err)
		return
	}
	defer rows.Close()

	var dbTickers []string
	for rows.Next() {
		var ticker string
		if err := rows.Scan(&ticker); err != nil {
			log.Printf("錯誤: 掃描 ticker 時出錯: %v", err)
			continue
		}
		dbTickers = append(dbTickers, ticker)
	}

	var delistedCount int
	for _, dbTicker := range dbTickers {
		if _, exists := masterList[dbTicker]; !exists {
			// Stock is in our DB but not in the new master list, so it's delisted.
			updateQuery := "UPDATE stocks SET is_active = false WHERE ticker = $1"
			_, err := dbpool.Exec(context.Background(), updateQuery, dbTicker)
			if err != nil {
				log.Printf("錯誤: 更新 %s 為非活躍狀態失敗: %v", dbTicker, err)
			} else {
				log.Printf("標記 %s 為已下市。", dbTicker)
				delistedCount++
			}
		}
	}
	log.Printf("處理完畢，共 %d 支股票被標記為已下市。", delistedCount)
}

// processTicker fetches and stores all data for a single stock.
func processTicker(ticker string, fmp *fmp.APIClient, dbpool *pgxpool.Pool, apiKey string) {
	// 步驟 1: 獲取公司 Profile
	profile, err := fmp.Stock.CompanyProfile(ticker)
	if err != nil {
		log.Printf("警告: 獲取 %s 的 Profile 失敗 (網路錯誤): %v", ticker, err)
		return
	}
	if len(profile) == 0 {
		log.Printf("警告: 獲取 %s 的 Profile 失敗 (FMP API 無此股票數據)。", ticker)
		return
	}
	p := profile[0]

	// 步驟 2: 準備並寫入 stocks 表
	sharesOutstanding := int64(0)
	if p.Price > 0 {
		sharesOutstanding = int64(float64(p.MktCap) / p.Price)
	}
	insertStockSQL := `
		INSERT INTO stocks (ticker, stock_name, exchange, industry, shares_outstanding, is_active)
		VALUES ($1, $2, $3, $4, $5, true)
		ON CONFLICT (ticker) DO UPDATE SET
			stock_name = EXCLUDED.stock_name, exchange = EXCLUDED.exchange,
			industry = EXCLUDED.industry, shares_outstanding = EXCLUDED.shares_outstanding, is_active = true;
	`
	_, err = dbpool.Exec(context.Background(), insertStockSQL, p.Symbol, p.CompanyName, p.ExchangeShortName, p.Industry, sharesOutstanding)
	if err != nil {
		log.Printf("錯誤: 無法將 %s 寫入 stocks 表: %v", ticker, err)
		return
	}

	// 步驟 3: 獲取歷史價格數據
	url := fmt.Sprintf("https://financialmodelingprep.com/api/v3/historical-price-full/%s?apikey=%s", ticker, apiKey)
	resp, err := http.Get(url)
	if err != nil {
		log.Printf("錯誤: 獲取 %s 的歷史數據時網路出錯: %v", ticker, err)
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("錯誤: 讀取 %s 的回應 body 失敗: %v", ticker, err)
		return
	}
	if resp.StatusCode != 200 {
		log.Printf("警告: FMP API 為 %s 的歷史數據回傳了 %d 狀態碼. 這通常意味著沒有可用的歷史數據。", ticker, resp.StatusCode)
		return
	}

	var historyData FmpHistoricalResponse
	err = json.Unmarshal(body, &historyData)
	if err != nil {
		log.Printf("警告: 解碼 %s 的歷史數據 JSON 失敗: %v", ticker, err)
		return
	}

	if len(historyData.Historical) == 0 {
		log.Printf("注意: %s 沒有返回任何歷史數據點。", ticker)
		return
	}

	// 步驟 4: 遍歷並寫入歷史數據
	for _, bar := range historyData.Historical {
		date, err := time.Parse("2006-01-02", bar.Date)
		if err != nil {
			log.Printf("警告: 解析 %s 的日期失敗: %v", ticker, err)
			continue
		}
		insertDailySQL := `
			INSERT INTO stock_daily_data (ticker, date, open, high, low, close, adj_close, volume)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
			ON CONFLICT (ticker, date) DO NOTHING; 
		`
		_, err = dbpool.Exec(context.Background(), insertDailySQL, ticker, date, bar.Open, bar.High, bar.Low, bar.Close, bar.AdjClose, bar.Volume)
		if err != nil {
			log.Printf("錯誤: 無法寫入 %s 在 %s 的日K數據: %v", ticker, date.Format("2006-01-02"), err)
		}
	}
}
