# ============================================================
# phase3/batch_signals.py
# Runs the signal engine across the entire watchlist
#
# HOW IT WORKS:
#   1. Grabs WATCHLIST from config.py
#   2. Loops through each ticker, generating a signal
#   3. Adds a small delay between API calls to avoid hitting
#      Anthropic rate limits (especially on free/tier-1 accounts)
#   4. Returns a list of all successful signals
# ============================================================

import time
from config import WATCHLIST
from phase3.signal_engine import generate_signal


def run_watchlist_signals(delay_seconds: float = 2.0, verbose: bool = True) -> list[dict]:
    """
    Run signal generation for every stock in the config.py WATCHLIST.
    
    Args:
        delay_seconds (float): Time to sleep between API calls to avoid rate limits.
        verbose (bool): Print progress to console.
        
    Returns:
        list[dict]: List of structured signal dictionaries.
    """
    all_signals = []
    total = len(WATCHLIST)
    
    if verbose:
        print("\n" + "=" * 60)
        print(f"  🚦 Phase 3: Batch Signal Generation ({total} stocks)")
        print("=" * 60)
        
    for i, ticker in enumerate(WATCHLIST, 1):
        if verbose:
            print(f"\n[{i}/{total}] Processing {ticker}...")
            
        # We need the company name for better semantic search.
        # We can extract it from the local ChromaDB stock_summaries collection,
        # but for simplicity and speed here we'll just use the ticker name
        # stripped of its suffix (e.g. RELIANCE.NS -> RELIANCE)
        company_name = ticker.replace(".NS", "").replace(".BO", "")
        
        try:
            # The generate_signal function handles retrieval, prompting, and parsing.
            signal_data = generate_signal(ticker, company_name, verbose=False)
            
            # Print a quick summary to the console so the user sees progress
            sig_value = signal_data.get("signal", "ERROR")
            conf      = signal_data.get("confidence", 0)
            
            # Console colors for quick visual parsing
            if sig_value == "BULLISH":
                color_sig = f"🟢 {sig_value}"
            elif sig_value == "BEARISH":
                color_sig = f"🔴 {sig_value}"
            elif sig_value == "HOLD":
                color_sig = f"🟡 {sig_value}"
            else:
                color_sig = f"❌ {sig_value}"
                
            if verbose:
                print(f"      ↳ {color_sig:<12} (Conf: {conf:>3}%)  "
                      f"⏱ {signal_data.get('latency_s', 0)}s")
                      
            all_signals.append(signal_data)
            
        except Exception as e:
            if verbose:
                print(f"      ↳ ❌ FAILED: {e}")
            all_signals.append({
                "ticker": ticker,
                "signal": "ERROR",
                "error": str(e)
            })
            
        # Rate limit safety pause (except after the last item)
        if i < total:
            time.sleep(delay_seconds)
            
    if verbose:
        print("\n" + "=" * 60)
        success = sum(1 for s in all_signals if s.get("signal") not in ("ERROR", "NEUTRAL"))
        print(f"  ✅ Batch complete. {len(all_signals)} signals generated.")
        print("=" * 60)
        
    return all_signals


if __name__ == "__main__":
    # Test run
    signals = run_watchlist_signals(delay_seconds=1.0)
    print(f"\nOutput subset test: {signals[0] if signals else 'No signals'}")
