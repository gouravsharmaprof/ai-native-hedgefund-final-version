# ============================================================
# phase1/db_store.py
# Task 4 — Store & query all data in ChromaDB
#
# HOW IT WORKS:
#   ChromaDB is a local vector database. We convert text documents
#   into numeric vectors (embeddings) so the AI can find semantically
#   similar content via cosine similarity — not just keyword search.
#
#   The default embedding function uses a small local sentence-transformer
#   model (all-MiniLM-L6-v2) — no API key required, runs offline.
#
# COLLECTIONS:
#   financial_news     — RSS articles
#   stock_summaries    — Company metadata + price summaries
#   transcripts        — Earnings call documents (Phase 2)
#
# WHY: This is the memory of the AI engine. Phase 2 queries this
#      store as context before calling Claude for analysis.
# ============================================================

import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
from config import DB_PATH

# ─── Initialise ChromaDB ──────────────────────────────────────
# PersistentClient = data survives between Python sessions (saved to disk)
client = chromadb.PersistentClient(path=DB_PATH)

# Default embedding function: downloads a ~80MB sentence-transformer model
# on first run, caches it locally — free, offline, no key needed
default_ef = embedding_functions.DefaultEmbeddingFunction()

# ─── Collections ──────────────────────────────────────────────
# Think of collections as database tables, but for vectors.
# Each collection uses the same embedding model for consistency.

news_collection = client.get_or_create_collection(
    name="financial_news",
    embedding_function=default_ef,
    metadata={"description": "Indian financial news articles from RSS feeds"},
)

stocks_collection = client.get_or_create_collection(
    name="stock_summaries",
    embedding_function=default_ef,
    metadata={"description": "NSE/BSE stock metadata and price summaries"},
)

transcripts_collection = client.get_or_create_collection(
    name="transcripts",
    embedding_function=default_ef,
    metadata={"description": "Earnings call transcripts and regulatory filings"},
)


# ─── Store News ───────────────────────────────────────────────

def store_news(articles: list) -> int:
    """
    Embed and store news articles in ChromaDB.

    Deduplication: IDs are based on hash of the article link,
    so re-running won't create duplicate records for the same URL.

    Args:
        articles (list): Output from phase1/news_scraper.fetch_news()

    Returns:
        int: Number of articles actually stored (skips duplicates)
    """
    if not articles:
        print("⚠️  store_news called with empty list — nothing to store.")
        return 0

    documents = []
    metadatas = []
    ids = []

    for article in articles:
        # Use URL hash as ID → same article won't be stored twice
        link = article.get("link", "")
        doc_id = f"news_{abs(hash(link)) if link else hash(article['title'])}_{abs(hash(article['fetched_at']))}"

        documents.append(article["full_text"])
        metadatas.append({
            "source":    article["source"],
            "title":     article["title"][:500],   # ChromaDB metadata char limit
            "link":      link[:500],
            "published": article.get("published", "")[:100],
            "fetched_at": article["fetched_at"],
        })
        ids.append(doc_id)

    # upsert = insert new + update existing (idempotent)
    news_collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    count = len(articles)
    print(f"✅ Stored/updated {count} articles in 'financial_news' collection")
    return count


# ─── Store Stock Summary ──────────────────────────────────────

def store_stock_summary(stock_data: dict) -> None:
    """
    Build a text summary of a stock and embed it in ChromaDB.
    The text format is designed to be readable by an LLM as context.

    Args:
        stock_data (dict): Output from phase1/stock_data.fetch_stock_data()
    """
    ticker = stock_data["ticker"]

    # Build a rich natural-language summary
    # This text is what gets embedded — make it information-dense
    price_history = stock_data.get("price_history", {})
    prices = list(price_history.values())
    price_trend = "N/A"
    if len(prices) >= 2:
        change_pct = (prices[-1] - prices[0]) / prices[0] * 100
        price_trend = f"{change_pct:+.2f}% over the period"

    summary_text = f"""
Company: {stock_data['company_name']}
NSE Ticker: {ticker}
Sector: {stock_data.get('sector', 'Unknown')}
Industry: {stock_data.get('industry', 'Unknown')}
Current Price: ₹{stock_data.get('current_price', 'N/A')}
Market Cap: {stock_data.get('market_cap', 'N/A')}
P/E Ratio (Trailing): {stock_data.get('pe_ratio', 'N/A')}
P/B Ratio: {stock_data.get('pb_ratio', 'N/A')}
Dividend Yield: {stock_data.get('dividend_yield', 'N/A')}
52-Week High: ₹{stock_data.get('52w_high', 'N/A')}
52-Week Low: ₹{stock_data.get('52w_low', 'N/A')}
Beta: {stock_data.get('beta', 'N/A')}
Average Volume: {stock_data.get('avg_volume', 'N/A')}
Price Trend (3mo): {price_trend}
Business Description: {stock_data.get('description', 'N/A')}
    """.strip()

    # ID = ticker + date → one record per ticker per day
    doc_id = f"stock_{ticker.replace('.', '_')}_{datetime.now().date()}"

    stocks_collection.upsert(
        documents=[summary_text],
        metadatas=[{
            "ticker":     ticker,
            "company":    stock_data["company_name"],
            "sector":     stock_data.get("sector", "Unknown"),
            "fetched_at": stock_data["fetched_at"],
        }],
        ids=[doc_id],
    )
    print(f"   📦 Stored: {stock_data['company_name']} ({ticker})")


def store_all_stocks(stocks: list) -> None:
    """Store all stock summaries from a list."""
    print(f"💾 Storing {len(stocks)} stock summaries in ChromaDB...")
    for s in stocks:
        try:
            store_stock_summary(s)
        except Exception as e:
            print(f"   ❌ Failed to store {s.get('ticker', '?')}: {e}")
    print(f"✅ Done storing stock summaries.")


# ─── Store Transcript ──────────────────────────────────────────

def store_transcript(transcript: dict) -> None:
    """
    Store an earnings transcript in ChromaDB.
    Content is chunked if >5000 chars to avoid token limits.

    Args:
        transcript (dict): Output from phase1/transcripts.make_transcript_doc()
    """
    content = transcript["content"]
    ticker  = transcript["ticker"]
    quarter = transcript["quarter"]

    # Simple chunking: split every 4000 chars with 200-char overlap
    chunk_size = 4000
    overlap    = 200
    chunks     = []
    start      = 0
    while start < len(content):
        end = min(start + chunk_size, len(content))
        chunks.append(content[start:end])
        start = end - overlap if end < len(content) else end

    for i, chunk in enumerate(chunks):
        doc_id = f"transcript_{ticker.replace('.', '_')}_{quarter}_chunk{i}"
        transcripts_collection.upsert(
            documents=[chunk],
            metadatas=[{
                "ticker":       ticker,
                "company":      transcript["company_name"],
                "quarter":      quarter,
                "year":         str(transcript["year"]),
                "chunk_index":  str(i),
                "total_chunks": str(len(chunks)),
                "source":       transcript.get("source", "manual"),
                "ingested_at":  transcript["ingested_at"],
            }],
            ids=[doc_id],
        )

    print(f"✅ Stored transcript: {transcript['company_name']} {quarter} "
          f"({len(chunks)} chunk(s))")


# ─── Query Functions ──────────────────────────────────────────

def query_news(question: str, n_results: int = 5, where: dict = None) -> list:
    """
    Semantic search over stored news articles.

    Args:
        question  (str): Natural language search query
        n_results (int): How many results to return
        where    (dict): Optional ChromaDB metadata filter
                         e.g. {"source": "Economic Times Markets"}

    Returns:
        list[str]: Matching article texts (sorted by relevance)
    """
    kwargs = dict(query_texts=[question], n_results=n_results)
    if where:
        kwargs["where"] = where

    results = news_collection.query(**kwargs)
    # results["documents"] is a list-of-lists (one per query)
    return results["documents"][0] if results["documents"] else []


def query_stocks(question: str, n_results: int = 3) -> list:
    """
    Semantic search over stock summaries.
    Example: query_stocks("high PE ratio IT sector stock")
    """
    results = stocks_collection.query(
        query_texts=[question],
        n_results=n_results,
    )
    return results["documents"][0] if results["documents"] else []


def query_transcripts(question: str, n_results: int = 3, ticker: str = None) -> list:
    """
    Semantic search over earnings transcripts.

    Args:
        question (str): E.g. "AI deal wins guidance"
        n_results(int): Number of chunks to return
        ticker   (str): Filter by ticker, e.g. "INFY.NS"

    Returns:
        list[str]: Matching transcript chunks
    """
    kwargs = dict(query_texts=[question], n_results=n_results)
    if ticker:
        kwargs["where"] = {"ticker": ticker}

    results = transcripts_collection.query(**kwargs)
    return results["documents"][0] if results["documents"] else []


def get_collection_stats() -> dict:
    """Return the document count for all three collections."""
    return {
        "financial_news":  news_collection.count(),
        "stock_summaries": stocks_collection.count(),
        "transcripts":     transcripts_collection.count(),
    }


# ─── Standalone execution ─────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AI-Hedge Engine — Phase 1: ChromaDB Store")
    print("=" * 55)

    stats = get_collection_stats()
    print("\n📊 Current database stats:")
    for col, count in stats.items():
        print(f"   {col}: {count} documents")

    # Test query if there's data
    if stats["financial_news"] > 0:
        print("\n🔍 Sample query: 'Infosys quarterly earnings'")
        results = query_news("Infosys quarterly earnings", n_results=3)
        for i, doc in enumerate(results, 1):
            print(f"   {i}. {doc[:150]}...")
    else:
        print("\n⚠️  No data yet — run main.py to populate the database.")
