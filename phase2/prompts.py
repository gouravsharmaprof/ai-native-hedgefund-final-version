# ============================================================
# phase2/prompts.py
# All Claude prompt templates for the RAG pipeline
#
# WHY a separate file?
#   Prompts are the "instructions" you give Claude. They are
#   the highest-leverage thing to tune — small wording changes
#   can dramatically improve output quality.
#   Keeping them here (not buried in engine code) makes them
#   easy to iterate on without touching logic.
# ============================================================


# ─── System Prompt ────────────────────────────────────────────
# This is the "personality" Claude adopts for every conversation.
# Think of it as the job description you'd give a human analyst.

SYSTEM_PROMPT = """You are an expert Indian equity research analyst at an AI-native hedge fund.

Your job is to answer questions about Indian stocks (NSE/BSE), financial news, and 
earnings calls — using ONLY the context documents provided to you. 

Rules you must follow:
1. Base your answer STRICTLY on the provided context. Do not invent or hallucinate facts.
2. If the context doesn't contain enough information to answer, say so clearly —
   e.g. "The provided documents don't contain sufficient information on this topic."
3. Always cite which source(s) you drew from at the end of your answer, like:
   "📚 Sources: [Source Name 1], [Source Name 2]"
4. Use Indian financial conventions (₹ for rupees, crore/lakh not million/billion).
5. Be concise but thorough. Bullet points are encouraged for clarity.
6. Do not give investment advice or tell the user to buy/sell — only summarise what 
   the documents say. Signals come in Phase 3.
"""


# ─── RAG Prompt Builder ───────────────────────────────────────

def build_rag_prompt(question: str, context_blocks: list[dict]) -> str:
    """
    Assemble the user-turn message that gets sent to Claude.

    The message embeds all retrieved context docs in a clearly
    labelled format so Claude knows exactly what it's working from.

    Args:
        question       (str):       The user's natural language question
        context_blocks (list[dict]): Each dict has keys:
                                       - "text"   : the document content
                                       - "source" : human-readable source label
                                       - "type"   : "news" | "transcript" | "stock"

    Returns:
        str: The fully assembled user message to pass to Claude
    """
    if not context_blocks:
        # No context found — ask Claude to say so gracefully
        return (
            f"Question: {question}\n\n"
            "No relevant documents were found in the knowledge base for this question. "
            "Please inform the user clearly and suggest they run Phase 1 data ingestion first."
        )

    # Format each context block with a numbered label
    context_parts = []
    for i, block in enumerate(context_blocks, 1):
        source_label = block.get("source", "Unknown Source")
        doc_type     = block.get("type", "document").upper()
        text         = block.get("text", "").strip()

        context_parts.append(
            f"[CONTEXT {i} — {doc_type} | {source_label}]\n{text}"
        )

    context_str = "\n\n" + ("\n\n" + "─" * 60 + "\n\n").join(context_parts)

    prompt = f"""Below are relevant documents retrieved from the knowledge base.
Use them to answer the question at the bottom. Cite your sources.

{'─' * 60}
{context_str}
{'─' * 60}

Question: {question}

Instructions:
- Answer based only on the above context.
- End your response with: 📚 Sources: [list the source names you actually used]
- If you cannot find a complete answer, say what you COULD find, then note what's missing.
"""
    return prompt


# ─── Signal Prompt (Phase 3 preview) ─────────────────────────
# This will be used in Phase 3 to generate structured buy/sell signals.
# Defined here now so the template is agreed on before we need it.

SIGNAL_SYSTEM_PROMPT = """You are a quantitative research engine for Indian equities.
Given news and transcript context, output a structured JSON signal.
Be conservative. When uncertain, use "NEUTRAL" as the signal.
"""

def build_signal_prompt(ticker: str, company_name: str, context_blocks: list[dict]) -> str:
    """
    Build the prompt for Phase 3 signal generation.
    Returns a prompt that asks Claude for a structured JSON output.
    (Placeholder — will be fully implemented in Phase 3.)
    """
    context_str = "\n\n".join(
        f"[{b.get('source', '?')}]\n{b['text']}"
        for b in context_blocks
    )

    return f"""Context about {company_name} ({ticker}):

{context_str}

Based ONLY on the above context, output a JSON object with this exact schema:
{{
  "ticker": "{ticker}",
  "signal": "BUY" | "SELL" | "NEUTRAL",
  "confidence": 0.0 to 1.0,
  "sentiment_score": -1.0 (very negative) to +1.0 (very positive),
  "key_reasons": ["reason 1", "reason 2", "reason 3"],
  "risks": ["risk 1", "risk 2"],
  "data_quality": "HIGH" | "MEDIUM" | "LOW"
}}

Respond with ONLY the JSON object — no explanation, no preamble."""
