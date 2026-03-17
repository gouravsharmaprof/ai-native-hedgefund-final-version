# ============================================================
# dashboard.py
# Streamlit Web UI for the AI-Native Financial Research Engine
#
# HOW TO RUN:
#   cd /Users/gouravsharma/.gemini/antigravity/scratch/ai-hedge-engine
#   streamlit run dashboard.py
# ============================================================

import os
import streamlit as st
import pandas as pd
from datetime import datetime

# Local imports
from config import WATCHLIST
from phase1.stock_data import fetch_all_stocks
from phase2.ingestor import seed_if_empty
from phase3.batch_signals import run_watchlist_signals
from phase3.report_generator import generate_markdown_report


# ─── Page Configuration ──────────────────────────────────────────

st.set_page_config(
    page_title="AI Hedge Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for signal badges
st.markdown("""
<style>
.signal-BULLISH { background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
.signal-BEARISH { background-color: #f8d7da; color: #721c24; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
.signal-HOLD    { background-color: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
.signal-ERROR   { background-color: #e2e3e5; color: #383d41; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ─── State Management ────────────────────────────────────────────

if 'signals' not in st.session_state:
    st.session_state.signals = []
if 'stocks_data' not in st.session_state:
    st.session_state.stocks_data = {}
if 'last_updated' not in st.session_state:
    st.session_state.last_updated = "Never"


# ─── Core Functions ──────────────────────────────────────────────

@st.cache_data(ttl=300) # Cache prices for 5 minutes
def get_live_prices():
    """Fetch live prices using Phase 1 logic."""
    stocks = fetch_all_stocks()
    # Convert list of dicts to a ticker-indexed map
    return {s['ticker']: s for s in stocks}


def run_pipeline():
    """Triggers the full refresh pipeline."""
    with st.spinner("Seeding ChromaDB if empty..."):
        seed_if_empty(force=False)
        
    with st.spinner("Fetching live prices..."):
        st.session_state.stocks_data = get_live_prices()
        
    with st.spinner("Generating AI Signals (this takes a minute)..."):
        # Run the full batch processor internally
        st.session_state.signals = run_watchlist_signals(delay_seconds=2.0, verbose=False)
        st.session_state.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save the report standard file for download
        generate_markdown_report(st.session_state.signals, "weekly_research_report.md")


# ─── Sidebar ─────────────────────────────────────────────────────

with st.sidebar:
    st.title("🤖 AI-Hedge Engine")
    st.markdown("Automated Financial Research")
    
    st.divider()
    
    st.markdown("### Controls")
    if st.button("🔄 Refresh Data & Signals", use_container_width=True, type="primary"):
        run_pipeline()
        st.success("Refreshed successfully!")
        
    # Download Report Button
    st.markdown("### Downloads")
    if os.path.exists("weekly_research_report.md"):
        with open("weekly_research_report.md", "r", encoding="utf-8") as f:
            report_data = f.read()
        
        st.download_button(
            label="📄 Download Weekly Report (.md)",
            data=report_data,
            file_name=f"Research_Report_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            use_container_width=True
        )
    else:
        st.info("Run a refresh to generate the weekly report.")
        
    st.divider()
    st.caption(f"Last updated: {st.session_state.last_updated}")


# ─── Main Content ────────────────────────────────────────────────

st.header("Watchlist Signals")

# If we haven't run yet, show a welcome message
if not st.session_state.signals:
    st.info("👈 Click **Refresh Data & Signals** in the sidebar to run the Claude-powered analysis engine.")
    st.stop()

# 1. Summary Metrics
bullish_cnt = sum(1 for s in st.session_state.signals if s.get("signal") == "BULLISH")
bearish_cnt = sum(1 for s in st.session_state.signals if s.get("signal") == "BEARISH")
hold_cnt    = sum(1 for s in st.session_state.signals if s.get("signal") == "HOLD")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Stocks", len(WATCHLIST))
col2.metric("🟢 Bullish", bullish_cnt)
col3.metric("🟡 Hold", hold_cnt)
col4.metric("🔴 Bearish", bearish_cnt)

st.divider()

# 2. Watchlist Table
# We use Streamlit Expanders to mimic an interactive table with drill-down details

for sig in st.session_state.signals:
    ticker = sig.get('ticker', 'UNKNOWN')
    signal_val = sig.get('signal', 'ERROR')
    conf = sig.get('confidence', 0)
    
    # Get live price data if available
    stock_info = st.session_state.stocks_data.get(ticker, {})
    price = stock_info.get('price', 'N/A')
    change = stock_info.get('change_pct', 0.0)
    
    # Format the header
    price_str = f"₹{price}" if price != 'N/A' else "N/A"
    change_str = f"({change:+.2f}%)" if isinstance(change, (int, float)) else ""
    
    # Header for the expander container
    header_col1, header_col2, header_col3 = st.columns([2, 1, 1])
    with header_col1:
        st.markdown(f"**{ticker}** | {price_str} {change_str}")
    with header_col2:
        st.markdown(f"<span class='signal-{signal_val}'>{signal_val}</span>", unsafe_allow_html=True)
    with header_col3:
        st.markdown(f"**Conf:** {conf}%")
        
    # The expandable row content
    with st.expander("View AI Analysis & Reasoning"):
        if signal_val == "ERROR":
            st.error(sig.get('error', 'An unknown error occurred.'))
        else:
            tcol1, tcol2 = st.columns(2)
            
            with tcol1:
                st.markdown("#### Key Drivers")
                for reason in sig.get("key_reasons", []):
                    st.markdown(f"- {reason}")
                    
                st.markdown(f"**Data Quality:** {sig.get('data_quality', 'UNKNOWN')}")
                st.markdown(f"**Sentiment Score:** {sig.get('sentiment_score', 0)} / 1.0")
                
            with tcol2:
                st.markdown("#### Risks / Headwinds")
                for risk in sig.get("risks", []):
                    st.markdown(f"- {risk}")
                    
                st.markdown("**Context Sources Used:**")
                for src in sig.get("sources_used", []):
                    st.markdown(f"- `{src}`")
    
    st.markdown("---")
