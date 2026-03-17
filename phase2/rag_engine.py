# ============================================================
# phase2/rag_engine.py
# Core RAG orchestrator — the brain of Phase 2
#
# FLOW:
#   User question
#       ↓
#   retriever.build_context()     ← searches ChromaDB
#       ↓
#   prompts.build_rag_prompt()    ← assembles the Gemini message
#       ↓
#   Gemini gemini-1.5-flash  ← generates grounded answer
#       ↓
#   RAGResponse dict              ← returned to caller
#
# WHY RAG (not pure LLM)?
#   Raw Gemini knows nothing about today's Infosys earnings or
#   Reliance's current PE ratio. RAG gives it a "working memory"
#   of real, fresh documents — so every answer is grounded,
#   traceable, and hallucination-resistant.
# ============================================================

import time
from dataclasses import dataclass, field
from google import genai
from google.genai import types

from phase2.retriever import build_context, check_db_has_data
from phase2.prompts   import SYSTEM_PROMPT, build_rag_prompt
from config           import GEMINI_API_KEY, GEMINI_MODEL, CLAUDE_MAX_TOKENS


# ─── Response Schema ──────────────────────────────────────────
# Every call to `ask()` returns one of these.
# Using a dataclass keeps the interface explicit and IDE-friendly.

@dataclass
class RAGResponse:
    """Structured response from the RAG engine."""

    question:     str                    # original user question
    answer:       str                    # Gemini's grounded answer
    sources:      list[str]              # e.g. ["Infosys Q3FY25 Transcript", "Financial News Feed"]
    context_used: list[dict]             # raw context blocks (for debugging)
    tokens_input:  int = 0              # tokens sent to Gemini
    tokens_output: int = 0              # tokens Gemini generated
    latency_s:    float = 0.0           # wall-clock time for the full call
    error:        str | None = None     # non-None if something went wrong

    def is_ok(self) -> bool:
        return self.error is None

    def pretty_print(self) -> None:
        """Print a nicely formatted response to the console."""
        divider = "─" * 60
        print(f"\n{divider}")
        print(f"❓ Question: {self.question}")
        print(divider)

        if not self.is_ok():
            print(f"❌ Error: {self.error}")
        else:
            print(f"\n{self.answer}")

        print(f"\n⚡ {self.latency_s:.1f}s  |  "
              f"↑{self.tokens_input} / ↓{self.tokens_output} tokens")
        print(divider)


# ─── RAG Engine Class ─────────────────────────────────────────

class RAGEngine:
    """
    Stateful RAG engine. Instantiate once, call ask() many times.

    Keeping state allows us to:
    - Reuse the Gemini model wrapper
    - Track conversation history in Phase 3 (multi-turn Q&A)
    - Cache repeated context lookups (future optimisation)
    """

    def __init__(self):
        """Initialise the Gemini client and validate DB state."""
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY is not set!\n"
                "Add your key to .env:\n"
                "  GEMINI_API_KEY=AI...-..."
            )

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self._db_stats = None   # lazily populated on first ask()

    def _ensure_db_ready(self) -> None:
        """
        Verify ChromaDB has data. Raises RuntimeError with helpful message if not.
        Only checked on the first call — cached after that.
        """
        if self._db_stats is None:
            self._db_stats = check_db_has_data()  # raises if empty

    def ask(
        self,
        question:    str,
        ticker_hint: str | None = None,
        verbose:     bool = True,
    ) -> RAGResponse:
        """
        The main public interface. Ask any financial question in natural language.

        Args:
            question    (str):        E.g. "What did Infosys say about margins?"
            ticker_hint (str | None): E.g. "INFY.NS" — focuses transcript search
                                      on a specific stock. Pass None to search broadly.
            verbose     (bool):       If True, prints retrieval + Gemini call progress.

        Returns:
            RAGResponse: Structured response with answer, sources, token counts, latency.

        Example:
            engine = RAGEngine()
            result = engine.ask("What is the latest news on Indian markets?")
            result.pretty_print()
        """
        t_start = time.time()

        # ── Guard: DB must have data ──────────────────────────
        try:
            self._ensure_db_ready()
        except RuntimeError as e:
            return RAGResponse(
                question=question,
                answer="",
                sources=[],
                context_used=[],
                error=str(e),
            )

        # ── Step 1: Retrieve context ──────────────────────────
        if verbose:
            print(f"\n🔎 Retrieving context for: '{question[:60]}...' "
                  if len(question) > 60 else f"\n🔎 Retrieving context for: '{question}'")

        try:
            context_blocks, source_names = build_context(question, ticker_hint)
        except Exception as e:
            return RAGResponse(
                question=question,
                answer="",
                sources=[],
                context_used=[],
                error=f"Retrieval failed: {e}",
            )

        # ── Step 2: Build the prompt ──────────────────────────
        user_message = build_rag_prompt(question, context_blocks)

        # ── Step 3: Call Gemini ───────────────────────────────
        if verbose:
            print(f"🤖 Calling Gemini ({GEMINI_MODEL})...")

        try:
            prompt = f"{SYSTEM_PROMPT}\n\n{user_message}"
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=CLAUDE_MAX_TOKENS,
                )
            )

            answer          = response.text
            tokens_input    = getattr(getattr(response, "usage_metadata", None), "prompt_token_count", 0)
            tokens_output   = getattr(getattr(response, "usage_metadata", None), "candidates_token_count", 0)
            latency         = time.time() - t_start

        except Exception as e:
            return RAGResponse(
                question=question,
                answer="",
                sources=source_names,
                context_used=context_blocks,
                latency_s=time.time() - t_start,
                error=f"Gemini API call failed: {e}",
            )

        return RAGResponse(
            question=question,
            answer=answer,
            sources=source_names,
            context_used=context_blocks,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_s=latency,
        )


# ─── Convenience function ─────────────────────────────────────
# A module-level singleton makes one-off scripts simpler:
#   from phase2.rag_engine import ask
#   answer = ask("What did Infosys say about margins?")

_engine: RAGEngine | None = None

def ask(question: str, ticker_hint: str | None = None, verbose: bool = True) -> RAGResponse:
    """
    Convenience wrapper. Creates a singleton RAGEngine and calls ask().

    Use this for scripts and notebooks. Use RAGEngine() directly if
    you need fine-grained lifecycle control.
    """
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine.ask(question, ticker_hint=ticker_hint, verbose=verbose)


# ─── Interactive Q&A loop ──────────────────────────────────────

def run_interactive_loop():
    """
    Start an interactive REPL for asking financial questions.
    Type 'exit' or 'quit' to stop. Type 'help' for tips.
    Called by main.py when --phase2 flag is passed.
    """
    from phase2.ingestor import seed_if_empty

    print("\n" + "=" * 60)
    print("  🤖 AI Financial Research Engine — RAG Q&A Mode")
    print("  Powered by Gemini + ChromaDB")
    print("=" * 60)
    print("  Type your question. Examples:")
    print("  → 'What did Infosys say about AI deals?'")
    print("  → 'Tell me about Reliance Industries finances'")
    print("  → 'Latest news on Indian stock markets'")
    print("  → 'ticker:INFY.NS What are the margin trends?'")
    print("  Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    # Make sure DB is seeded before going into the loop
    print("\n🌱 Checking ChromaDB...")
    seed_if_empty()

    engine = RAGEngine()
    session_count = 0

    while True:
        try:
            raw_input = input("\n💬 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Goodbye!")
            break

        if not raw_input:
            continue

        if raw_input.lower() in ("exit", "quit", "q"):
            print("👋 Exiting RAG mode. Goodbye!")
            break

        if raw_input.lower() == "help":
            print("\n📖 Tips:")
            print("  • Prefix with 'ticker:TICKER ' to focus on a stock")
            print("    e.g. 'ticker:INFY.NS What did management say about hiring?'")
            print("  • Ask about news, earnings, or stock fundamentals")
            print("  • Type 'stats' to see ChromaDB doc counts")
            continue

        if raw_input.lower() == "stats":
            from phase1.db_store import get_collection_stats
            stats = get_collection_stats()
            print("\n📊 ChromaDB Stats:")
            for k, v in stats.items():
                print(f"   {k}: {v} docs")
            continue

        # ── Parse optional ticker: prefix ─────────────────────
        # Lets users focus on a specific stock:
        #   "ticker:INFY.NS What did management say about margins?"
        ticker_hint = None
        question    = raw_input

        if raw_input.lower().startswith("ticker:"):
            parts = raw_input.split(" ", 1)
            if len(parts) == 2:
                ticker_hint = parts[0].split(":")[1].strip().upper()
                question    = parts[1].strip()
                print(f"   📌 Focusing on ticker: {ticker_hint}")

        # ── Ask ───────────────────────────────────────────────
        result = engine.ask(question, ticker_hint=ticker_hint, verbose=True)
        result.pretty_print()
        session_count += 1


# ─── Standalone execution ──────────────────────────────────────
if __name__ == "__main__":
    run_interactive_loop()
