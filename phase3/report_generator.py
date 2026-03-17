# ============================================================
# phase3/report_generator.py
# Formats structured JSON signals into a weekly research report
#
# HOW IT WORKS:
#   1. Takes a list of dictionaries output by batch_signals.py
#   2. Sorts them by Bullish -> Hold -> Bearish -> Error
#   3. Generates a clean Markdown document (weekly_report.md)
# ============================================================

from datetime import datetime
import json


def _group_signals(signals: list[dict]) -> dict:
    """Group signals by their call (BULLISH, BEARISH, HOLD, ERROR)."""
    groups = {
        "BULLISH": [],
        "BEARISH": [],
        "HOLD": [],
        "ERROR": []
    }
    
    for s in signals:
        sig_type = s.get("signal", "ERROR").upper()
        if sig_type in groups:
            groups[sig_type].append(s)
        else:
            groups["ERROR"].append(s)
            
    # Sort each group by confidence descending
    for k in groups:
        groups[k].sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
    return groups


def generate_markdown_report(signals: list[dict], output_path: str = "weekly_report.md") -> str:
    """
    Generate a formatted markdown report from raw signal data.
    
    Args:
        signals (list[dict]): Output from batch_signals.py
        output_path (str): Where to save the file
        
    Returns:
        str: The generated markdown text
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    groups = _group_signals(signals)
    
    # Header & Summary
    md = [
        f"# AI-Native Financial Research Engine",
        f"## Weekly Signal Report — {date_str}",
        f"\n**Total Stocks Analyzed:** {len(signals)}",
        f"- 🟢 **Bullish:** {len(groups['BULLISH'])}",
        f"- 🟡 **Hold:** {len(groups['HOLD'])}",
        f"- 🔴 **Bearish:** {len(groups['BEARISH'])}",
        f"- ❌ **Errors/Neutral:** {len(groups['ERROR'])}",
        "\n---"
    ]
    
    # Detail Sections (Iterate over groups in order)
    sections = [
        ("🟢 BULLISH SIGNALS", "BULLISH"),
        ("🟡 HOLD SIGNALS", "HOLD"),
        ("🔴 BEARISH SIGNALS", "BEARISH"),
        ("❌ ERRORS / INCOMPLETE DATA", "ERROR")
    ]
    
    for title, key in sections:
        if not groups[key]:
            continue
            
        md.append(f"\n## {title}")
        
        for sig in groups[key]:
            ticker = sig.get("ticker", "UNKNOWN")
            
            # Error handling block
            if key == "ERROR":
                err_msg = sig.get("error", "Unknown processing error")
                md.append(f"### {ticker}")
                md.append(f"> **Error:** {err_msg}\n")
                continue
                
            # Valid signal block
            conf  = sig.get("confidence", 0)
            sent  = sig.get("sentiment_score", 0.0)
            qual  = sig.get("data_quality", "UNKNOWN")
            
            md.append(f"### {ticker} — Confidence: {conf}%")
            md.append(f"- **Sentiment Score:** {sent} (-1.0 to 1.0)")
            md.append(f"- **Data Quality:** {qual}")
            
            md.append("\n**Key Reasons:**")
            for reason in sig.get("key_reasons", []):
                md.append(f"- {reason}")
                
            md.append("\n**Risks / Headwinds:**")
            for risk in sig.get("risks", []):
                md.append(f"- {risk}")
                
            md.append("\n**Sources Used:**")
            sources = sig.get("sources_used", [])
            if sources:
                for src in sources:
                    md.append(f"- {src}")
            else:
                md.append("- *No verified sources found.*")
                
            md.append("\n***\n")
            
    # Compile
    full_text = "\n".join(md)
    
    # Save to disk
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
        
    return full_text


if __name__ == "__main__":
    # Test layout with mock data
    mock_data = [
        {
            "ticker": "INFY.NS",
            "signal": "BULLISH",
            "confidence": 85,
            "sentiment_score": 0.7,
            "key_reasons": ["Strong margin expansion", "Generative AI deal wins"],
            "risks": ["US macro uncertainty"],
            "data_quality": "HIGH",
            "sources_used": ["Infosys Q3FY25 Transcript", "Economic Times"]
        },
        {
            "ticker": "RELIANCE.NS",
            "signal": "HOLD",
            "confidence": 60,
            "sentiment_score": 0.1,
            "key_reasons": ["Retail growth steady", "Telecom ARPU stagnant"],
            "risks": ["High capex cycle"],
            "data_quality": "MEDIUM",
            "sources_used": ["Stock Fundamentals"]
        }
    ]
    
    print(generate_markdown_report(mock_data, "test_report.md"))
    print("Mock report generated at test_report.md")
