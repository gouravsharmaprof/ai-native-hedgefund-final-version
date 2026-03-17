# ============================================================
# phase1/stock_data.py
# Task 1 — Pull live + historical price data for Indian stocks
#
# HOW IT WORKS:
#   yfinance wraps Yahoo Finance's API. NSE stocks use the ".NS"
#   suffix (e.g. "RELIANCE.NS"). We pull metadata (PE, market cap,
#   52-week range) AND historical closing prices for the past 3 months.
#
# WHY: This gives the AI raw price context before generating signals.
# ============================================================

import yfinance as yf
import json
from datetime import datetime
from config import WATCHLIST, DEFAULT_PERIOD, STOCK_DATA_OUTPUT


def fetch_stock_data(ticker: str, period: str = DEFAULT_PERIOD) -> dict:
    """
    Fetch stock metadata + price history for a single NSE ticker.

    Args:
        ticker (str): NSE ticker with .NS suffix, e.g. "RELIANCE.NS"
        period (str): Lookback window — "1d", "1mo", "3mo", "6mo", "1y"

    Returns:
        dict: Company metadata + price history + fetch timestamp
    """
    stock = yf.Ticker(ticker)

    # .history() returns a DataFrame with OHLCV columns
    hist = stock.history(period=period)

    # .info is a dict of company fundamentals (can be slow ~1-2s per call)
    info = stock.info

    # Build a clean, flat dict we can store in ChromaDB or JSON
    result = {
        "ticker":         ticker,
        "company_name":   info.get("longName", ticker),
        "sector":         info.get("sector", "Unknown"),
        "industry":       info.get("industry", "Unknown"),
        "current_price":  info.get("currentPrice") or stock.fast_info.get("lastPrice") or info.get("regularMarketPrice"),
        "market_cap":     info.get("marketCap"),
        "pe_ratio":       info.get("trailingPE"),
        "pb_ratio":       info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "52w_high":       info.get("fiftyTwoWeekHigh"),
        "52w_low":        info.get("fiftyTwoWeekLow"),
        "avg_volume":     info.get("averageVolume"),
        "beta":           info.get("beta"),           # market risk measure
        "description":    info.get("longBusinessSummary", "")[:500],  # truncate

        # Price history: {ISO-date-string → closing price}
        # .to_dict() on df index produces Timestamp keys → convert to str
        "price_history": {
            str(k.date()): round(float(v), 2)
            for k, v in hist["Close"].items()
        },

        "fetched_at": datetime.now().isoformat(),
    }

    return result


def fetch_all_stocks(period: str = DEFAULT_PERIOD) -> list:
    """
    Fetch data for every stock in WATCHLIST (from config.py).

    Returns:
        list[dict]: One dict per ticker, in watchlist order.
    """
    all_data = []

    for ticker in WATCHLIST:
        print(f"📡 Fetching {ticker}...")
        try:
            data = fetch_stock_data(ticker, period)
            all_data.append(data)
            price_str = f"₹{data['current_price']}" if data["current_price"] else "N/A"
            print(f"   ✅ {data['company_name']} — {price_str}")
        except Exception as e:
            print(f"   ❌ Failed for {ticker}: {e}")

    return all_data


def get_price_change(stock_data: dict) -> dict:
    """
    Calculate price change metrics from historical data.

    Args:
        stock_data (dict): A dict returned by fetch_stock_data()

    Returns:
        dict: {change_1d, change_1w, change_1mo, change_pct_1mo}
    """
    prices = list(stock_data["price_history"].values())

    if not prices or len(prices) < 2:
        return {}

    current  = prices[-1]
    day_ago  = prices[-2]  if len(prices) >= 2  else current
    week_ago = prices[-6]  if len(prices) >= 6  else prices[0]
    month_ago= prices[-22] if len(prices) >= 22 else prices[0]

    return {
        "change_1d":      round(current - day_ago, 2),
        "change_1w":      round(current - week_ago, 2),
        "change_1mo":     round(current - month_ago, 2),
        "change_pct_1mo": round((current - month_ago) / month_ago * 100, 2),
    }


# ─── Standalone execution ─────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AI-Hedge Engine — Phase 1: Stock Data Fetch")
    print("=" * 55)

    stocks = fetch_all_stocks()

    # Attach price-change metrics to each stock
    for s in stocks:
        s["price_changes"] = get_price_change(s)

    # Save raw output as JSON so you can inspect it easily
    with open(STOCK_DATA_OUTPUT, "w") as f:
        json.dump(stocks, f, indent=2, default=str)

    print(f"\n✅ Saved data for {len(stocks)} stocks → {STOCK_DATA_OUTPUT}")

    # Quick summary table
    print("\n📊 Summary:")
    print(f"{'Ticker':<20} {'Price':>10} {'1mo%':>8} {'PE':>8}")
    print("-" * 50)
    for s in stocks:
        chg = s.get("price_changes", {}).get("change_pct_1mo", 0)
        pe  = s.get("pe_ratio", "N/A")
        price = s.get("current_price", "N/A")
        print(f"{s['ticker']:<20} {str(price):>10} {str(chg):>8} {str(pe):>8}")
