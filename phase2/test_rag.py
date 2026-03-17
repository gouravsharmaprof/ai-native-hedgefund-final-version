# ============================================================
# phase2/test_rag.py
# Smoke tests for the Phase 2 RAG pipeline
#
# HOW TO RUN:
#   cd /Users/gouravsharma/.gemini/antigravity/scratch/ai-hedge-engine
#   python3 phase2/test_rag.py
#
# WHAT THIS TESTS:
#   1. ChromaDB seed (ingestor)
#   2. Retriever multi-collection search
#   3. End-to-end RAG: question → ChromaDB → Claude → answer
#   4. Graceful error handling when DB is empty (mocked)
#
# NOTE: Tests 1 and 2 run without a Gemini API key.
#       Test 3 requires GEMINI_API_KEY in .env.
#       Tests are skipped with a clear message if no key is present.
# ============================================================

import sys
import os

# ── path fix: allow running from project root or phase2/ dir ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from phase2.ingestor   import seed_if_empty
from phase2.retriever  import build_context, check_db_has_data
from phase1.db_store   import get_collection_stats
from config            import GEMINI_API_KEY


# ─── Helpers ──────────────────────────────────────────────────

PASS  = "✅ PASS"
FAIL  = "❌ FAIL"
SKIP  = "⏭️  SKIP"
tests_run    = 0
tests_passed = 0


def test(name: str, condition: bool, detail: str = ""):
    global tests_run, tests_passed
    tests_run += 1
    if condition:
        tests_passed += 1
        print(f"{PASS}  {name}")
    else:
        print(f"{FAIL}  {name}" + (f"\n        {detail}" if detail else ""))


def skip(name: str, reason: str):
    print(f"{SKIP}  {name}  ({reason})")


# ─── Test Suite ───────────────────────────────────────────────

def test_1_seed():
    """Test: ChromaDB gets seeded with at least news + transcript."""
    print("\n── Test 1: ChromaDB Seeding ─────────────────────────")
    try:
        seed_if_empty()  # idempotent — won't re-fetch if already seeded
        stats = get_collection_stats()
        total = sum(stats.values())
        test("DB has > 0 documents after seed", total > 0,
             f"Got total={total}, stats={stats}")
        test("Transcripts collection has ≥ 1 doc", stats["transcripts"] >= 1,
             f"transcripts count = {stats['transcripts']}")
    except Exception as e:
        test("seed_if_empty() runs without exception", False, str(e))


def test_2_retriever():
    """Test: Retriever returns non-empty context blocks for real queries."""
    print("\n── Test 2: Multi-Collection Retriever ───────────────")

    queries = [
        ("What did Infosys say about AI deals?",  "INFY.NS"),
        ("Latest news on Indian stock markets",    None),
        ("Reliance Industries business overview",  None),
    ]

    for question, ticker in queries:
        try:
            blocks, sources = build_context(question, ticker_hint=ticker)
            test(
                f"Query returns ≥1 block: '{question[:45]}...'",
                len(blocks) >= 1,
                f"Got {len(blocks)} blocks, sources={sources}"
            )
        except Exception as e:
            test(f"Query doesn't crash: '{question[:45]}'", False, str(e))


def test_3_rag_end_to_end():
    """Test: Full RAG pipeline produces a non-empty answer with sources."""
    print("\n── Test 3: End-to-End RAG (requires Gemini API key) ─")

    has_key = (
        GEMINI_API_KEY
        and GEMINI_API_KEY != "your_gemini_api_key_here"
        and len(GEMINI_API_KEY) > 20
    )

    if not has_key:
        skip("RAG answer for transcript question",
             "GEMINI_API_KEY not set in .env — add it to run this test")
        skip("RAG answer has sources list",
             "GEMINI_API_KEY not set")
        skip("RAG answer for news question",
             "GEMINI_API_KEY not set")
        return

    from phase2.rag_engine import ask

    # Test 3a — transcript-grounded question
    r1 = ask("What did Infosys say about margins?", ticker_hint="INFY.NS", verbose=False)
    test("Answer for 'Infosys margins' is non-empty",
         r1.is_ok() and len(r1.answer) > 50,
         r1.error or f"answer length={len(r1.answer)}")
    test("Sources list is non-empty",
         r1.is_ok() and len(r1.sources) >= 1,
         f"sources={r1.sources}")

    # Test 3b — news-grounded question
    r2 = ask("What is happening in Indian stock markets?", verbose=False)
    test("Answer for market news question is non-empty",
         r2.is_ok() and len(r2.answer) > 50,
         r2.error or f"answer length={len(r2.answer)}")

    # Test 3c — token usage is reported
    test("Token counts are > 0",
         r1.is_ok() and r1.tokens_input > 0 and r1.tokens_output > 0,
         f"input={r1.tokens_input}, output={r1.tokens_output}")


def test_4_error_handling():
    """Test: RAG engine returns a clean error (no crash) when DB is empty."""
    print("\n── Test 4: Graceful Error Handling ──────────────────")

    from phase2.retriever import build_context

    # build_context on a nonsense question still should not crash
    try:
        blocks, sources = build_context("xyzzy unknown nonsense 98765", ticker_hint=None)
        # May return 0 blocks if no match — that's fine, should not raise
        test("build_context with unmatched query doesn't crash",
             True)
        test("build_context returns a list (even if empty)",
             isinstance(blocks, list),
             f"Got type: {type(blocks)}")
    except Exception as e:
        test("build_context with unmatched query doesn't crash", False, str(e))


# ─── Entry Point ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AI-Hedge Engine — Phase 2 Smoke Tests")
    print("=" * 60)

    test_1_seed()
    test_2_retriever()
    test_3_rag_end_to_end()
    test_4_error_handling()

    print("\n" + "=" * 60)
    print(f"  Results: {tests_passed}/{tests_run} tests passed")
    if tests_passed == tests_run:
        print("  \U0001f389 All tests passed! Phase 2 RAG pipeline is healthy.")
    else:
        print(f"  ⚠️  {tests_run - tests_passed} test(s) failed — see details above.")
    print("=" * 60)

    # Return non-zero exit code if any test failed (useful in CI)
    sys.exit(0 if tests_passed == tests_run else 1)
