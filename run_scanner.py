#!/usr/bin/env python3
"""
EasyMoney CLI Scanner
Runs BigBeluga Institutional Demand Zone (Order Block) Scanner
with configurable strength / buy conviction threshold.
"""

import sys
import argparse
import pandas as pd
from engine import fetch_nse_symbols, run_full_screener

def main():
    parser = argparse.ArgumentParser(description="EasyMoney Institutional Order Block Scanner (≥60% Strength)")
    parser.add_argument("--universe", type=str, default="Nifty 50", choices=["Nifty 50", "Nifty 200", "Nifty 500"], help="NSE Universe")
    parser.add_argument("--strength", type=float, default=60.0, help="Minimum Buy Conviction Strength percent (default: 60)")
    parser.add_argument("--retest-only", action="store_true", help="Only show stocks actively retesting the demand box")
    parser.add_argument("--sw-len", type=int, default=3, help="Swing pivot lookback length (default: 3)")
    parser.add_argument("--atr-mult", type=float, default=1.2, help="ATR displacement multiplier (default: 1.2)")
    parser.add_argument("--csv", type=str, default=None, help="Optional output CSV filepath")
    args = parser.parse_args()

    print("=" * 80)
    print(f"  EASYMONEY INSTITUTIONAL DEMAND ZONE SCANNER")
    print(f"  Universe       : {args.universe}")
    print(f"  Min Strength   : {args.strength:.1f}% Buy Conviction")
    print(f"  Retest Filter  : {'Only Active Retests' if args.retest_only else 'All Valid Zones'}")
    print(f"  Timeframe      : 15-Minute Intraday")
    print("=" * 80)

    print(f"\n[1/3] Fetching constituents for {args.universe}...")
    symbols = fetch_nse_symbols(args.universe)
    print(f"      Retrieved {len(symbols)} tickers.")

    print(f"\n[2/3] Ingesting 15m OHLCV data & running quantitative algorithm...")
    
    def on_progress(cur, tot, msg):
        pct = int((cur / max(1, tot)) * 100)
        sys.stdout.write(f"\r      Progress: [{pct:>3}%] {cur}/{tot} tickers processed")
        sys.stdout.flush()

    summary_df, processed_dfs, symbol_zones = run_full_screener(
        symbols=symbols,
        sw_len=args.sw_len,
        atr_mult=args.atr_mult,
        buy_pct_thresh=args.strength / 100.0,
        require_retest=args.retest_only,
        progress_callback=on_progress
    )
    print("\n      Scan completed successfully!\n")

    print("[3/3] SCANNER RESULTS:")
    print("=" * 80)

    if summary_df.empty:
        print("  No setups found matching the criteria.")
        return

    retest_df = summary_df[summary_df["Is Retesting"] == True]
    above_df = summary_df[summary_df["Is Retesting"] == False]

    display_cols = [
        "Symbol", "Current Price (₹)", "Demand Box Range",
        "Buy Conviction (%)", "Relative Vol (RVOL)", "2R Target (₹)", "Retesting"
    ]

    pd.set_option("display.max_rows", 100)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.width", 120)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    if not retest_df.empty:
        print(f"\n🟢 ACTIVELY RETESTING DEMAND BOX ({len(retest_df)} Setups):")
        print("-" * 80)
        print(retest_df[display_cols].to_string(index=False))

    if not above_df.empty and not args.retest_only:
        print(f"\n⚪ HOLDING ABOVE DEMAND BOX ({len(above_df)} Setups):")
        print("-" * 80)
        print(above_df[display_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print(f"Summary: {len(summary_df)} total active order blocks detected | {len(retest_df)} actively in retest zone.")
    print("=" * 80)

    if args.csv:
        summary_df.to_csv(args.csv, index=False)
        print(f"Results exported to {args.csv}")

if __name__ == "__main__":
    main()
