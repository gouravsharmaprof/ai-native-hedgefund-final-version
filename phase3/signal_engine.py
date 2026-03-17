# ============================================================
# phase3/signal_engine.py
# Core signal generation logic for a single stock
#
# HOW IT WORKS:
#   1. Takes a ticker (e.g. "RELIANCE.NS")
#   2. Pulls multi-context from ChromaDB (News + Transcripts + Fundamentals)
#   3. Passes context to Gemini with a strict JSON-schema prompt
#   4. Parses Gemini's output into a Python dict
#
# WHY JSON MODE?
#   For downstream automation (like trading bots or rigid reports),
#   we need predictable, parser-friendly output from the LLM,
#   not a chatty paragraph.
# ============================================================

import time
import json
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, CLAUDE_MAX_TOKENS
from phase2.retriever import build_context, check_db_has_data
from phase2.prompts   import SIGNAL_SYSTEM_PROMPT, build_signal_prompt


class SignalEngine:
    """Stateful engine for generating stock signals via Gemini."""

    def __init__(self):
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is missing from .env")
            
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        # Ensure DB is ready
        check_db_has_data()

    def generate_signal(self, ticker: str, company_name: str, verbose: bool = False) -> dict:
        """
        Generate a structured buy/sell signal for a specific stock.
        
        Args:
            ticker       (str): NSE symbol, e.g. "INFY.NS"
            company_name (str): Full name, e.g. "Infosys"
            verbose      (bool): Print progress
            
        Returns:
            dict: Parsed JSON with standard signal schema
        """
        t_start = time.time()
        
        if verbose:
            print(f"\n🧠 Generating signal for {ticker} ({company_name})...")
            
        # ── Step 1: Retrieve context ──────────────────────────
        # We query the company name to pull relevant news/transcripts.
        # We pass the ticker_hint so the retriever strictly matches
        # the earnings transcripts to this specific stock.
        context_blocks, sources = build_context(company_name, ticker_hint=ticker)
        
        # If we got absolutely zero context, we can't generate a credible signal
        if not context_blocks:
            return self._build_error_signal(
                ticker, 
                "No data found in ChromaDB for this stock. Run Phase 1 ingestion."
            )

        # Calculate data quality
        # High = we found lots of docs; Low = we only found 1 or 2 chunks
        data_quality = "HIGH" if len(context_blocks) >= 4 else "MEDIUM" if len(context_blocks) >= 2 else "LOW"

        # ── Step 2: Build prompt ──────────────────────────────
        user_message = build_signal_prompt(ticker, company_name, context_blocks)
        
        # ── Step 3: Call Gemini ───────────────────────────────
        try:
            prompt = f"{SIGNAL_SYSTEM_PROMPT}\n\n{user_message}"
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=CLAUDE_MAX_TOKENS,
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            raw_text = response.text
            
            # ── Step 4: Parse JSON ────────────────────────────
            signal_data = self._parse_json_from_llm(raw_text)
            
            # Append our metadata
            signal_data["sources_used"] = sources
            signal_data["data_quality"] = data_quality
            signal_data["latency_s"]    = round(time.time() - t_start, 1)
            signal_data["error"]        = None
            
            if verbose:
                print(f"   ✅ Signal generated: {signal_data.get('signal', 'ERROR')} "
                      f"(Confidence: {signal_data.get('confidence', 0)}%)")
                
            return signal_data
            
        except Exception as e:
            return self._build_error_signal(ticker, f"Gemini API or parsing failed: {e}")

    def _parse_json_from_llm(self, text: str) -> dict:
        """
        Safely extract and parse JSON from Gemini's response.
        Sometimes LLMs wrap JSON in ```json ... ``` markdown blocks.
        """
        text = text.strip()
        
        # Strip markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Gemini output as JSON. Raw output:\n{text}\nError: {e}")
            
    def _build_error_signal(self, ticker: str, error_msg: str) -> dict:
        """Return a safe fallback dictionary if something crashes."""
        return {
            "ticker": ticker,
            "signal": "ERROR",
            "confidence": 0,
            "sentiment_score": 0.0,
            "key_reasons": ["Generation failed"],
            "risks": [error_msg],
            "data_quality": "ERROR",
            "sources_used": [],
            "latency_s": 0.0,
            "error": error_msg
        }

# Singleton for ease of use in scripts
_engine = None

def generate_signal(ticker: str, company_name: str, verbose: bool = False) -> dict:
    global _engine
    if _engine is None:
        _engine = SignalEngine()
    return _engine.generate_signal(ticker, company_name, verbose)


if __name__ == "__main__":
    print("Testing single-stock signal logic...")
    # Clean output test for Infosys
    res = generate_signal("INFY.NS", "Infosys", verbose=True)
    print(json.dumps(res, indent=2))
