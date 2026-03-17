# ============================================================
# config.py — Central configuration for AI-Native Financial Research Engine
# All constants, API keys, and settings live here.
# Import this in every module: from config import WATCHLIST, CLAUDE_API_KEY etc.
# ============================================================

import os
from dotenv import load_dotenv

# Load variables from .env file (create one if you haven't already)
# .env should contain: CLAUDE_API_KEY=sk-ant-...
load_dotenv()

# ─── Watchlist ──────────────────────────────────────────────
# These are NSE-listed stocks. The ".NS" suffix is required by yfinance
# to pull data from Yahoo Finance's NSE feed.
WATCHLIST = [
    "RELIANCE.NS",    # Reliance Industries
    "TCS.NS",         # Tata Consultancy Services
    "INFY.NS",        # Infosys
    "HDFCBANK.NS",    # HDFC Bank
    "WIPRO.NS",       # Wipro
    "TATAMOTORS.NS",  # Tata Motors
    "BAJFINANCE.NS",  # Bajaj Finance
    "ADANIENT.NS",    # Adani Enterprises
]

# ─── Gemini API ──────────────────────────────────────────────
# Best practice: store in .env, not hardcoded here
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Which model to use
GEMINI_MODEL = "gemini-2.5-flash"

# ─── ChromaDB ────────────────────────────────────────────────
# Local directory where ChromaDB persists all vector data
# This folder is created automatically on first run
DB_PATH = "./chroma_db"

# ─── News Feeds ──────────────────────────────────────────────
# Free RSS feeds — no API key needed
# These cover most major Indian financial news sources
NEWS_FEEDS = {
    "Economic Times Markets":
        "https://economictimes.indiatimes.com/markets/rss.cms",
    "MoneyControl":
        "https://www.moneycontrol.com/rss/latestnews.xml",
    "LiveMint Markets":
        "https://www.livemint.com/rss/markets",
    "Business Standard":
        "https://www.business-standard.com/rss/markets-106.rss",
}

# ─── Data Fetch Settings ─────────────────────────────────────
# Default lookback period for historical price data
# Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
DEFAULT_PERIOD = "3mo"

# Max news articles fetched per RSS feed per run
MAX_NEWS_PER_FEED = 20

# ─── File Paths ──────────────────────────────────────────────
# Local JSON files used for debugging and cache inspection
STOCK_DATA_OUTPUT = "./stock_data.json"
NEWS_DATA_OUTPUT  = "./news_data.json"

# ─── Phase 2: RAG Settings ───────────────────────────────────
# How many results to pull from each ChromaDB collection per query.
# Tune these to balance context richness vs. token cost.
RAG_NEWS_RESULTS       = 5    # news articles (most up-to-date)
RAG_TRANSCRIPT_RESULTS = 3    # transcript chunks (most authoritative)
RAG_STOCK_RESULTS      = 2    # stock fundamental summaries

# Total character budget for context fed to Claude.
# All retrieved chunks are trimmed together to stay under this.
# Approx rule: 1 token ≈ 4 chars; claude-sonnet has 200k token context.
# 8000 chars ≈ ~2000 tokens — leaves plenty of room for the answer.
MAX_CONTEXT_CHARS = 8_000

# Max tokens Claude will generate in its answer.
# 1024 is sufficient for a detailed research summary.
# Raise to 2048 if you want longer comparative reports.
CLAUDE_MAX_TOKENS = 4096
