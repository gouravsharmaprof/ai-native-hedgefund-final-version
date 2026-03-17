# ============================================================
# phase2/ingestor.py
# Ensures ChromaDB is populated with Phase 1 data before RAG runs
#
# HOW IT WORKS:
#   Acts as a "seed" step — checks if ChromaDB is empty, and if so,
#   fetches news + loads the sample transcript and stores them.
#   Also re-runs ingestion on demand (e.g. daily refresh).
#
# WHY SEPARATE FROM db_store.py?
#   db_store.py is a low-level storage layer (pure CRUD).
#   This file is high-level orchestration — it decides WHAT to fetch,
#   WHEN to fetch it, and calls db_store to persist it.
# ============================================================

from datetime import datetime
from phase1.news_scraper  import fetch_news
from phase1.transcripts   import get_sample_transcript
from phase1.db_store      import (
    store_news,
    store_transcript,
    get_collection_stats,
)


def seed_if_empty(force: bool = False) -> dict:
    """
    Check ChromaDB; if empty (or force=True), run ingestion.

    This is the "smart" entry point — calling it many times is safe.
    Subsequent calls skip ingestion if the DB already has data.

    Args:
        force (bool): If True, re-ingest even if DB has data.
                      Use this for a daily refresh.

    Returns:
        dict: Collection stats after (potential) ingestion
    """
    stats = get_collection_stats()
    total = sum(stats.values())

    if total > 0 and not force:
        print(f"✅ ChromaDB already has data ({total} docs total). Skipping seed.")
        print(f"   Tip: call seed_if_empty(force=True) to refresh.")
        return stats

    reason = "force refresh" if force else "DB is empty"
    print(f"\n🌱 Seeding ChromaDB ({reason})...")
    print("─" * 55)

    return run_ingestion()


def run_ingestion() -> dict:
    """
    Run the full Phase 1 ingestion pipeline:
      1. Fetch news from RSS feeds → store in ChromaDB
      2. Load sample Infosys Q3FY25 transcript → store in ChromaDB

    Returns:
        dict: Final collection stats
    """
    results = {"news_stored": 0, "transcripts_stored": 0}

    # ── Step 1: News ─────────────────────────────────────────
    print("\n📰 Fetching financial news from RSS feeds...")
    try:
        articles = fetch_news()
        if articles:
            results["news_stored"] = store_news(articles)
        else:
            print("   ⚠️  No articles fetched — check network / feed URLs in config.py")
    except Exception as e:
        print(f"   ❌ News ingestion failed: {e}")

    # ── Step 2: Sample Transcript ─────────────────────────────
    # In Phase 1 we have one hard-coded sample (Infosys Q3FY25).
    # Phase 2 will extend this to real BSE filings + PDF parsing.
    print("\n📝 Loading sample Infosys Q3FY25 earnings transcript...")
    try:
        transcript = get_sample_transcript()
        store_transcript(transcript)
        results["transcripts_stored"] = 1
    except Exception as e:
        print(f"   ❌ Transcript ingestion failed: {e}")

    # ── Final stats ───────────────────────────────────────────
    stats = get_collection_stats()
    print(f"\n✅ Ingestion complete at {datetime.now().strftime('%H:%M:%S')}")
    print(f"   financial_news  : {stats['financial_news']} docs")
    print(f"   stock_summaries : {stats['stock_summaries']} docs")
    print(f"   transcripts     : {stats['transcripts']} docs")

    return stats


# ─── Standalone execution ──────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AI-Hedge Engine — Phase 2: Data Ingestor")
    print("=" * 55)

    import sys
    force = "--force" in sys.argv

    if force:
        print("🔄 Force mode: re-ingesting all data...")

    stats = seed_if_empty(force=force)
    print(f"\n📊 Final DB state: {stats}")
