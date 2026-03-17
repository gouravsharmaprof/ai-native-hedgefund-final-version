# ============================================================
# main.py — Orchestrator for AI-Native Financial Research Engine
#
# WHAT THIS DOES:
#   Phase 1 (default): Ingest NSE stock prices, news, transcripts
#   Phase 2 (--phase2): Launch interactive RAG Q&A powered by Claude
#
# HOW TO RUN:
#   python3 main.py                   ← Full Phase 1 ingestion
#   python3 main.py --no-stocks       ← Skip slow stock fetch
#   python3 main.py --no-news         ← Skip news fetch
#   python3 main.py --query-only      ← Skip ingestion, just test queries
#   python3 main.py --phase2          ← Launch RAG Q&A with Claude
#   python3 main.py --phase2 --refresh ← Re-ingest data then launch RAG
# ============================================================

import sys
import time
import json
import argparse
from datetime import datetime

# Phase 1 modules
from phase1.stock_data   import fetch_all_stocks
from phase1.news_scraper import fetch_news
from phase1.transcripts  import get_sample_transcript
from phase1.db_store     import (
    store_news,
    store_all_stocks,
    store_transcript,
    query_news,
    query_stocks,
    query_transcripts,
    get_collection_stats,
)
from config import STOCK_DATA_OUTPUT, NEWS_DATA_OUTPUT


# ─── Argument Parser ──────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="AI-Hedge Engine — Data Ingestion + RAG Q&A"
    )
    # ── Phase 1 flags ──────────────────────────────────────────────────
    parser.add_argument("--no-stocks",   action="store_true",
                        help="Skip stock price fetch (faster for dev)")
    parser.add_argument("--no-news",     action="store_true",
                        help="Skip news RSS fetch")
    parser.add_argument("--no-transcripts", action="store_true",
                        help="Skip transcript ingestion")
    parser.add_argument("--query-only",  action="store_true",
                        help="Skip all ingestion, only run test queries")

    # ── Phase 2 flags ──────────────────────────────────────────────────
    parser.add_argument("--phase2",      action="store_true",
                        help="Launch interactive RAG Q&A mode (Claude)")
    parser.add_argument("--refresh",     action="store_true",
                        help="Force re-ingest news/transcripts before Phase 2/3")

    # ── Phase 3 flags ──────────────────────────────────────────────────
    parser.add_argument("--phase3",      action="store_true",
                        help="Generate the full automated Weekly Research Report")

    return parser.parse_args()


# ─── Step Runners ─────────────────────────────────────────────

def run_stock_ingestion() -> list:
    """Fetch stock data and store in ChromaDB. Returns fetched stock list."""
    print("\n" + "─" * 55)
    print("📈  STEP 1 — Stock Data Ingestion")
    print("─" * 55)

    t0 = time.time()
    stocks = fetch_all_stocks()

    if stocks:
        # Save JSON snapshot for inspection
        with open(STOCK_DATA_OUTPUT, "w") as f:
            json.dump(stocks, f, indent=2, default=str)
        print(f"\n   💾 JSON snapshot → {STOCK_DATA_OUTPUT}")

        # Embed and store in ChromaDB
        store_all_stocks(stocks)
    else:
        print("   ⚠️  No stock data fetched — check network / ticker symbols.")

    print(f"   ⏱  Done in {time.time() - t0:.1f}s")
    return stocks


def run_news_ingestion() -> list:
    """Fetch RSS news and store in ChromaDB. Returns fetched article list."""
    print("\n" + "─" * 55)
    print("📰  STEP 2 — Financial News Ingestion")
    print("─" * 55)

    t0 = time.time()
    articles = fetch_news()

    if articles:
        # Save JSON snapshot
        with open(NEWS_DATA_OUTPUT, "w") as f:
            json.dump(articles, f, indent=2)
        print(f"\n   💾 JSON snapshot → {NEWS_DATA_OUTPUT}")

        # Store in ChromaDB
        store_news(articles)
    else:
        print("   ⚠️  No articles fetched. Check RSS feed URLs in config.py.")

    print(f"   ⏱  Done in {time.time() - t0:.1f}s")
    return articles


def run_transcript_ingestion():
    """Load and store the sample earnings transcript."""
    print("\n" + "─" * 55)
    print("📝  STEP 3 — Earnings Transcript Ingestion")
    print("─" * 55)

    transcript = get_sample_transcript()
    store_transcript(transcript)
    print(f"   ✅ Sample transcript stored: {transcript['company_name']} "
          f"{transcript['quarter']}")


def run_verification_queries():
    """
    Run 3 semantic queries to confirm ChromaDB is working correctly.
    This is your smoke test — if these return sensible results, the
    whole ingestion pipeline is healthy.
    """
    print("\n" + "─" * 55)
    print("🔍  STEP 4 — Verification Queries")
    print("─" * 55)

    # Query 1: News search
    print("\n[Query 1] News: 'Reliance Industries quarterly results'")
    news_results = query_news("Reliance Industries quarterly results", n_results=3)
    if news_results:
        for i, doc in enumerate(news_results, 1):
            print(f"   {i}. {doc[:120]}...")
    else:
        print("   ⚠️  No results — run with stock/news ingestion first.")

    # Query 2: Stock search
    print("\n[Query 2] Stocks: 'IT sector high growth company'")
    stock_results = query_stocks("IT sector high growth company", n_results=2)
    if stock_results:
        for i, doc in enumerate(stock_results, 1):
            print(f"   {i}. {doc[:150]}...")
    else:
        print("   ⚠️  No stock summaries stored yet.")

    # Query 3: Transcript search
    print("\n[Query 3] Transcripts: 'AI deal wins guidance revenue'")
    tr_results = query_transcripts("AI deal wins guidance revenue", n_results=2)
    if tr_results:
        for i, doc in enumerate(tr_results, 1):
            print(f"   {i}. {doc[:150]}...")
    else:
        print("   ⚠️  No transcripts stored yet.")


def print_db_stats():
    """Print how many documents are in each ChromaDB collection."""
    print("\n" + "─" * 55)
    print("📊  ChromaDB Collection Stats")
    print("─" * 55)
    stats = get_collection_stats()
    for col, count in stats.items():
        bar = "█" * min(count // 2, 40)
        print(f"   {col:<22} {count:>5} docs  {bar}")


# ─── Main Entry Point ─────────────────────────────────────────

def main():
    args = parse_args()

    # ── Phase 3 branch: Weekly Signal Report ────────────────────────────
    # If --phase3 is passed, run the batch signal generator and save report.
    if args.phase3:
        from phase2.ingestor         import seed_if_empty
        from phase3.batch_signals    import run_watchlist_signals
        from phase3.report_generator import generate_markdown_report

        print("=" * 60)
        print("  📈 AI-Native Financial Research Engine")
        print("  Phase 3 — Weekly Signal Report Generation")
        print("=" * 60)

        seed_if_empty(force=args.refresh)

        # Generate signals
        t0 = time.time()
        signals = run_watchlist_signals(delay_seconds=2.0)
        
        # Format and save report
        report_path = "weekly_research_report.md"
        generate_markdown_report(signals, output_path=report_path)
        
        print(f"\n✅ Report generated in {time.time() - t0:.1f}s")
        print(f"📄 Saved to: ./{report_path}")
        return

    # ── Phase 2 branch: RAG Q&A mode ────────────────────────────────────
    # If --phase2 is passed, skip Phase 1 and launch the RAG REPL.
    # Use --refresh to force re-ingest of news + transcripts first.
    if args.phase2:
        from phase2.ingestor   import seed_if_empty
        from phase2.rag_engine import run_interactive_loop

        print("=" * 60)
        print("  🤖 AI-Native Financial Research Engine")
        print("  Phase 2 — RAG Q&A Mode (Claude + ChromaDB)")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Seed ChromaDB if empty (or force refresh if --refresh passed)
        seed_if_empty(force=args.refresh)

        # Launch interactive Q&A REPL
        run_interactive_loop()
        return

    # ── Phase 1 branch: data ingestion ──────────────────────────────────
    print("=" * 55)
    print("  🤖 AI-Native Financial Research Engine")
    print("  Phase 1 — Data Ingestion Pipeline")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    if not args.query_only:
        if not args.no_stocks:
            run_stock_ingestion()

        if not args.no_news:
            run_news_ingestion()

        if not args.no_transcripts:
            run_transcript_ingestion()
    else:
        print("\n⚡  --query-only mode: skipping ingestion")

    # Always run verification queries
    run_verification_queries()

    # Always show final stats
    print_db_stats()

    print("\n" + "=" * 55)
    print("  ✅  Phase 1 Complete!")
    print("  🚀 Ready for Phase 2:  python3 main.py --phase2")
    print("  🚀 Ready for Phase 3:  python3 main.py --phase3")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
