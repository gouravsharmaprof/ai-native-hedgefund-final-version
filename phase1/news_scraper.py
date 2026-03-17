# ============================================================
# phase1/news_scraper.py
# Task 2 — Scrape financial news from Indian RSS feeds
#
# HOW IT WORKS:
#   feedparser parses any RSS/Atom XML feed into a Python object.
#   We pull from 4 major Indian financial news sources without
#   needing any API key. The resulting article dicts are ready
#   to be embedded and stored in ChromaDB.
#
# WHY: News sentiment is a leading indicator — market moves often
#      happen BEFORE price action is reflected in charts.
# ============================================================

import feedparser
import re
from datetime import datetime
from config import NEWS_FEEDS, MAX_NEWS_PER_FEED


def _clean_html(raw: str) -> str:
    """Strip HTML tags from RSS summaries (some feeds include HTML markup)."""
    clean = re.sub(r"<[^>]+>", " ", raw)   # remove tags
    clean = re.sub(r"\s+", " ", clean)      # collapse whitespace
    return clean.strip()


def fetch_news(max_per_feed: int = MAX_NEWS_PER_FEED) -> list:
    """
    Fetch latest financial news articles from all configured RSS feeds.

    Each article dict contains:
        - source, title, summary, link, published, fetched_at
        - full_text: concatenated title + summary for embedding in ChromaDB

    Args:
        max_per_feed (int): Max articles to pull per source (default 20)

    Returns:
        list[dict]: All articles across all sources
    """
    all_articles = []

    for source, url in NEWS_FEEDS.items():
        print(f"📰 Fetching news from {source}...")
        try:
            # feedparser handles HTTP fetching + XML parsing in one call
            feed = feedparser.parse(url)

            if feed.bozo:
                # "bozo" flag = feed has parsing issues (still usable usually)
                print(f"   ⚠️  Feed has minor parse issues — continuing anyway")

            count = 0
            for entry in feed.entries[:max_per_feed]:
                raw_summary = entry.get("summary", "")
                clean_summary = _clean_html(raw_summary)
                title = entry.get("title", "").strip()

                # Skip empty entries
                if not title:
                    continue

                article = {
                    "source":     source,
                    "title":      title,
                    "summary":    clean_summary[:1000],   # cap at 1000 chars
                    "link":       entry.get("link", ""),
                    "published":  entry.get("published", ""),
                    "fetched_at": datetime.now().isoformat(),

                    # full_text = what gets vectorized and stored in ChromaDB
                    # Combining title + summary gives richer semantic search
                    "full_text":  f"{title}. {clean_summary}"[:2000],
                }
                all_articles.append(article)
                count += 1

            print(f"   ✅ Got {count} articles")

        except Exception as e:
            print(f"   ❌ Failed for {source}: {e}")

    return all_articles


def filter_news_by_company(articles: list, company_name: str) -> list:
    """
    Filter articles that mention a specific company name.

    Checks both the title and the summary (case-insensitive).

    Args:
        articles (list): Output from fetch_news()
        company_name (str): E.g. "Reliance", "TCS", "Infosys"

    Returns:
        list[dict]: Filtered articles mentioning the company
    """
    term = company_name.lower()
    return [
        a for a in articles
        if term in a["title"].lower() or term in a["summary"].lower()
    ]


def filter_news_by_ticker(articles: list, ticker: str) -> list:
    """
    Filter by NSE ticker symbol (e.g. "RELIANCE", "TCS").
    Strips the ".NS" suffix automatically before matching.
    """
    # "RELIANCE.NS" → "RELIANCE"
    symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
    return [
        a for a in articles
        if symbol in a["title"].upper() or symbol in a["summary"].upper()
    ]


def get_news_summary_by_company(articles: list, company_name: str) -> str:
    """
    Return a single string combining recent headlines about a company.
    Used as context input when calling Claude for sentiment analysis.

    Args:
        articles (list): Output from fetch_news()
        company_name (str): Company name to filter by

    Returns:
        str: Joined headlines string, or "No recent news found."
    """
    relevant = filter_news_by_company(articles, company_name)
    if not relevant:
        return f"No recent news found for {company_name}."

    lines = []
    for i, a in enumerate(relevant[:10], 1):  # cap at 10 headlines
        lines.append(f"{i}. [{a['source']}] {a['title']}")

    return "\n".join(lines)


# ─── Standalone execution ─────────────────────────────────────
if __name__ == "__main__":
    import json
    from config import NEWS_DATA_OUTPUT

    print("=" * 55)
    print("  AI-Hedge Engine — Phase 1: News Scraper")
    print("=" * 55)

    articles = fetch_news()
    print(f"\n✅ Total articles fetched: {len(articles)}")

    # Save full output as JSON
    with open(NEWS_DATA_OUTPUT, "w") as f:
        json.dump(articles, f, indent=2)
    print(f"   Saved → {NEWS_DATA_OUTPUT}")

    # Show a quick company-filter demo
    print("\n📌 Sample — Reliance mentions:")
    reliance = filter_news_by_company(articles, "Reliance")
    print(f"   Found {len(reliance)} articles")
    for a in reliance[:3]:
        print(f"   → {a['title'][:90]}")
