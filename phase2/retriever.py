# ============================================================
# phase2/retriever.py
# Multi-collection context builder for the RAG pipeline
#
# HOW IT WORKS:
#   Given a user question, this module searches ALL THREE
#   ChromaDB collections simultaneously, then merges the results
#   into a single ranked list of context blocks.
#
#   The blocks are labeled by type (NEWS / TRANSCRIPT / STOCK)
#   so Claude can see where each piece of info came from.
#
# WHY MULTI-COLLECTION?
#   A question like "What did Infosys say about margins, and how
#   is their stock performing?" requires BOTH transcript data AND
#   stock fundamental data. A single-collection search would miss
#   half the answer.
# ============================================================

from phase1.db_store import (
    query_news,
    query_stocks,
    query_transcripts,
    get_collection_stats,
)
from config import (
    RAG_NEWS_RESULTS,
    RAG_TRANSCRIPT_RESULTS,
    RAG_STOCK_RESULTS,
    MAX_CONTEXT_CHARS,
)


def build_context(
    question:    str,
    ticker_hint: str | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Search all three ChromaDB collections and compile a context block list.

    This is the "R" (Retrieval) step of RAG.

    Args:
        question    (str):        The natural language question
        ticker_hint (str | None): Optional NSE ticker to bias transcript search,
                                  e.g. "INFY.NS" → search transcripts for Infosys only

    Returns:
        tuple[list[dict], list[str]]:
            - context_blocks: list of dicts with keys "text", "source", "type"
              (these go straight into prompts.build_rag_prompt)
            - source_names:   deduplicated list of source strings (for the citations line)
    """
    context_blocks = []
    char_budget    = MAX_CONTEXT_CHARS  # stay inside LLM context window

    # ── 1. Transcript Search ──────────────────────────────────
    # Transcripts are the most authoritative source — they are direct
    # statements from company management. Search these first.
    print(f"   🔍 Searching transcripts... (ticker_hint={ticker_hint})")
    try:
        tr_docs = query_transcripts(question, n_results=RAG_TRANSCRIPT_RESULTS, ticker=ticker_hint)
        for doc in tr_docs:
            if char_budget <= 0:
                break
            trimmed = doc[:min(len(doc), char_budget)]
            char_budget -= len(trimmed)
            context_blocks.append({
                "text":   trimmed,
                "source": _infer_transcript_source(trimmed),
                "type":   "transcript",
            })
    except Exception as e:
        print(f"   ⚠️  Transcript search failed: {e}")

    # ── 2. News Search ────────────────────────────────────────
    # News gives recency — transcripts may be months old but news
    # is today's market reality.
    print(f"   🔍 Searching financial news...")
    try:
        news_docs = query_news(question, n_results=RAG_NEWS_RESULTS)
        for doc in news_docs:
            if char_budget <= 0:
                break
            trimmed = doc[:min(len(doc), char_budget)]
            char_budget -= len(trimmed)
            context_blocks.append({
                "text":   trimmed,
                "source": "Financial News Feed",
                "type":   "news",
            })
    except Exception as e:
        print(f"   ⚠️  News search failed: {e}")

    # ── 3. Stock Fundamentals Search ─────────────────────────
    # Adds valuation context (PE, market cap, 52w range) that
    # neither news nor transcripts reliably contain.
    print(f"   🔍 Searching stock fundamentals...")
    try:
        stock_docs = query_stocks(question, n_results=RAG_STOCK_RESULTS)
        for doc in stock_docs:
            if char_budget <= 0:
                break
            trimmed = doc[:min(len(doc), char_budget)]
            char_budget -= len(trimmed)
            context_blocks.append({
                "text":   trimmed,
                "source": "Stock Fundamentals",
                "type":   "stock",
            })
    except Exception as e:
        print(f"   ⚠️  Stock search failed: {e}")

    # ── 4. Deduplicate source names ───────────────────────────
    source_names = list(dict.fromkeys(b["source"] for b in context_blocks))

    chars_used = MAX_CONTEXT_CHARS - char_budget
    print(f"   ✅ Retrieved {len(context_blocks)} context blocks "
          f"({chars_used:,} chars / {MAX_CONTEXT_CHARS:,} budget)")

    return context_blocks, source_names


def check_db_has_data() -> dict:
    """
    Check if ChromaDB has been populated. Returns stats dict.
    Raises a RuntimeError with a helpful message if the DB is empty.

    Call this before running RAG queries to give the user a clear
    error rather than a confusing empty-answer response.
    """
    stats = get_collection_stats()
    total = sum(stats.values())

    if total == 0:
        raise RuntimeError(
            "ChromaDB is empty! Run Phase 1 ingestion first:\n"
            "  python3 main.py          (full run)\n"
            "  python3 main.py --no-stocks  (faster — news + transcripts only)"
        )

    return stats


def _infer_transcript_source(text: str) -> str:
    """
    Try to extract a human-readable source label from transcript text.
    Looks for 'Company:' or 'Q3FY' style patterns to build a nice label.
    Falls back to a generic label if nothing is found.
    """
    import re

    # Look for "Infosys Q3FY25 Earnings Call" style patterns
    match = re.search(r"(Q\dFY\d{2,4})", text)
    quarter = match.group(1) if match else ""

    # Look for company name
    company_match = re.search(r"Company:\s*(.+)", text)
    company = company_match.group(1).strip() if company_match else ""

    if company and quarter:
        return f"{company} {quarter} Transcript"
    elif company:
        return f"{company} Transcript"
    elif quarter:
        return f"Earnings Transcript {quarter}"
    else:
        return "Earnings Transcript"
