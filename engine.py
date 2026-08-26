"""
BigBeluga Quantitative Order Block Engine & NSE Data Orchestrator
Optimized for 15-Minute Institutional Demand Zone Scanning
"""

import io
import time
import requests
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Callable

# Standard HTTP headers mimicking a modern browser
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

# Reliable fallback universe of high-liquidity Nifty constituents
FALLBACK_TOP25_NSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "LICI.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ONGC.NS", "KOTAKBANK.NS", "TITAN.NS", "NTPC.NS", "AXISBANK.NS",
    "TATACONSUM.NS", "ULTRACEMCO.NS", "WIPRO.NS", "POWERGRID.NS", "M&M.NS"
]

NSE_ARCHIVE_URLS = {
    "Nifty 50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "Nifty 200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "Nifty 500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
}


def fetch_nse_symbols(universe: str = "Nifty 50") -> List[str]:
    """
    Fetches official live CSV constituents directly from NSE Archives.
    Appends .NS suffix for Yahoo Finance compatibility.
    Falls back gracefully if network blocks request.
    """
    url = NSE_ARCHIVE_URLS.get(universe)
    if not url:
        return FALLBACK_TOP25_NSE.copy()

    try:
        session = requests.Session()
        resp = session.get(url, headers=DEFAULT_HEADERS, timeout=8)
        if resp.status_code == 200 and len(resp.content) > 50:
            df = pd.read_csv(io.StringIO(resp.text))
            col_match = [c for c in df.columns if c.strip().lower() == "symbol"]
            if col_match:
                sym_col = col_match[0]
                symbols = [
                    f"{str(s).strip().upper()}.NS"
                    for s in df[sym_col].dropna()
                    if str(s).strip() and not str(s).strip().startswith("NIFTY")
                ]
                if symbols:
                    # Clean out common symbols known to cause Yahoo 404 delisting issues
                    clean_symbols = [s for s in symbols if s not in ["TATAMOTORS.NS"]]
                    if "TATAMOTORS.NS" in symbols:
                        clean_symbols.append("TMPV.NS") # Updated or alternative if needed
                    return clean_symbols
    except Exception as e:
        print(f"[fetch_nse_symbols] Failed fetching {universe} ({e}), reverting to fallback list.")

    return FALLBACK_TOP25_NSE.copy()


def fetch_single_ticker_direct(symbol: str, period: str = "5d", interval: str = "15m") -> Optional[pd.DataFrame]:
    """
    Ultra-fast direct Yahoo Finance v8 chart API fetcher for single tickers.
    Bypasses crumb/cookie bottlenecks.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={period}"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=6)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return None
        res0 = result[0]
        timestamps = res0.get("timestamp")
        if not timestamps:
            return None
        
        quote = res0.get("indicators", {}).get("quote", [{}])[0]
        df = pd.DataFrame({
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume")
        }, index=pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("Asia/Kolkata"))
        
        df.dropna(subset=["Open", "High", "Low", "Close", "Volume"], inplace=True)
        if len(df) >= 15:
            return df
    except Exception:
        pass
    return None


def fetch_chunk_yfinance(chunk: List[str], period: str = "5d", interval: str = "15m") -> Dict[str, pd.DataFrame]:
    """
    Downloads intraday data for a chunk of up to 50 tickers using yfinance.
    """
    results: Dict[str, pd.DataFrame] = {}
    if not chunk:
        return results

    try:
        df = yf.download(
            chunk,
            period=period,
            interval=interval,
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=False
        )

        if df is not None and not df.empty:
            if len(chunk) == 1:
                # Single ticker result
                s = chunk[0]
                if isinstance(df.columns, pd.MultiIndex):
                    sub = df.xs(s, axis=1, level=1) if s in df.columns.levels[1] else df[s]
                else:
                    sub = df.copy()
                sub.dropna(subset=["Open", "High", "Low", "Close", "Volume"], inplace=True)
                if len(sub) >= 15:
                    results[s] = sub
            else:
                # Multi-ticker result
                for s in chunk:
                    try:
                        if s in df.columns.levels[0]:
                            sub = df[s].dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
                            if len(sub) >= 15:
                                results[s] = sub
                    except Exception:
                        pass
    except Exception as e:
        print(f"[fetch_chunk_yfinance] Warning on chunk: {e}")

    # Fallback to direct fetch for any missing tickers in chunk
    missing = [s for s in chunk if s not in results]
    if missing:
        for s in missing:
            direct_df = fetch_single_ticker_direct(s, period=period, interval=interval)
            if direct_df is not None:
                results[s] = direct_df

    return results


def fetch_all_intraday_data(
    symbols: List[str],
    period: str = "5d",
    interval: str = "15m",
    chunk_size: int = 50,
    max_workers: int = 4,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, pd.DataFrame]:
    """
    Parallelized batch data ingestion in concurrent chunks of 50 tickers.
    """
    chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
    total_symbols = len(symbols)
    completed_symbols = 0
    all_data: Dict[str, pd.DataFrame] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {
            executor.submit(fetch_chunk_yfinance, chunk, period, interval): chunk
            for chunk in chunks
        }
        for future in as_completed(future_to_chunk):
            chunk = future_to_chunk[future]
            try:
                chunk_res = future.result()
                all_data.update(chunk_res)
            except Exception as e:
                print(f"[fetch_all_intraday_data] Error downloading chunk: {e}")
            
            completed_symbols += len(chunk)
            if progress_callback:
                progress_callback(min(completed_symbols, total_symbols), total_symbols, f"Ingested {len(all_data)}/{total_symbols} stocks...")

    return all_data


def calculate_bigbeluga_order_blocks(
    df: pd.DataFrame,
    sw_len: int = 3,
    atr_mult: float = 1.2,
    buy_pct_thresh: float = 0.60
) -> Tuple[pd.DataFrame, List[dict]]:
    """
    Calculates BigBeluga Volume-Weighted Order Block Quantitative Algorithm.
    
    1. TR & 14-period ATR
    2. 10-period Volume SMA & RVOL
    3. Intra-bar Buy Volume Ratio: Buy_Pct = (Close - Low) / (High - Low)
    4. Swing Low Pivot Detection with lookback sw_len
    5. Displacement Check: Max Close after pivot >= Low + Multiplier * ATR
    6. Volume Conviction: Buy_Pct >= Threshold and Volume >= Vol_SMA
    7. Zone Boundaries: Bottom = Low, Top = max(Open, Close)
    8. Invalidation check: Close < Bottom invalidates zone
    9. Retest Detection: Bottom * 0.998 <= Current Price <= Top * 1.005
    """
    df = df.copy()
    n = len(df)
    if n < 20:
        return df, []

    # Ensure numeric columns
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["Open", "High", "Low", "Close", "Volume"], inplace=True)
    n = len(df)
    if n < 20:
        return df, []

    # 1. True Range & ATR (14-period SMA)
    h_l = df["High"] - df["Low"]
    h_cp = (df["High"] - df["Close"].shift(1)).abs()
    l_cp = (df["Low"] - df["Close"].shift(1)).abs()
    df["TR"] = pd.concat([h_l, h_cp, l_cp], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(14).mean()

    # 2. Volume SMA (10-period SMA) & Relative Volume (RVOL)
    df["Vol_SMA"] = df["Volume"].rolling(10).mean()
    df["RVOL"] = np.where(df["Vol_SMA"] > 0, df["Volume"] / df["Vol_SMA"], 1.0)

    # 3. Intra-bar Buy Volume Ratio
    hl_range = df["High"] - df["Low"]
    df["Buy_Pct"] = np.where(hl_range > 0, (df["Close"] - df["Low"]) / hl_range, 0.5)

    detected_zones = []

    for i in range(sw_len, n - 1):
        low_i = df["Low"].iloc[i]
        
        # Check swing low pivot
        left_window = df["Low"].iloc[max(0, i - sw_len):i]
        left_min = left_window.min() if not left_window.empty else low_i
        
        right_len = min(sw_len, n - 1 - i)
        right_window = df["Low"].iloc[i + 1:i + 1 + right_len]
        right_min = right_window.min() if not right_window.empty else low_i

        if low_i <= left_min and low_i <= right_min:
            atr_i = df["ATR"].iloc[i]
            if pd.isna(atr_i) or atr_i <= 0:
                continue

            # Check displacement in next 1-3 bars
            disp_window = df["Close"].iloc[i + 1:min(n, i + 4)]
            if disp_window.empty:
                continue
            max_disp_close = disp_window.max()
            displacement = max_disp_close - low_i
            has_displacement = displacement >= (atr_mult * atr_i)

            # Volume conviction on pivot or breakout candle
            pivot_buy_pct = df["Buy_Pct"].iloc[i]
            next_buy_pct = df["Buy_Pct"].iloc[i + 1] if i + 1 < n else 0.0
            best_buy_pct = max(pivot_buy_pct, next_buy_pct)

            pivot_vol = df["Volume"].iloc[i]
            pivot_vol_sma = df["Vol_SMA"].iloc[i]
            next_vol = df["Volume"].iloc[i + 1] if i + 1 < n else 0.0
            next_vol_sma = df["Vol_SMA"].iloc[i + 1] if i + 1 < n else 1.0

            vol_confirmed = (pivot_vol >= pivot_vol_sma) or (next_vol >= next_vol_sma)
            conviction_ok = (best_buy_pct >= buy_pct_thresh) and vol_confirmed

            if has_displacement and conviction_ok:
                bottom = float(low_i)
                top = float(max(df["Open"].iloc[i], df["Close"].iloc[i]))

                # Invalidation check: Did any subsequent candle close below bottom?
                subsequent_closes = df["Close"].iloc[i + 1:]
                is_invalidated = bool((subsequent_closes < bottom).any())

                if not is_invalidated:
                    current_price = float(df["Close"].iloc[-1])
                    is_retesting = bool(bottom * 0.998 <= current_price <= top * 1.005)
                    
                    # Risk-to-Reward calculation
                    risk = max(0.01, top - bottom)
                    target_2r = top + (2 * risk)
                    target_3r = top + (3 * risk)

                    detected_zones.append({
                        "pivot_index": i,
                        "pivot_time": df.index[i],
                        "bottom": round(bottom, 2),
                        "top": round(top, 2),
                        "box_range_str": f"₹{bottom:.2f} - ₹{top:.2f}",
                        "box_height": round(top - bottom, 2),
                        "box_height_pct": round(((top - bottom) / bottom) * 100, 2),
                        "atr": round(atr_i, 2),
                        "displacement": round(displacement, 2),
                        "disp_atr_ratio": round(displacement / atr_i, 2),
                        "buy_pct": round(best_buy_pct * 100, 1),
                        "rvol": round(float(df["RVOL"].iloc[i]), 2),
                        "current_price": round(current_price, 2),
                        "is_retesting": is_retesting,
                        "retest_status": "🟢 Retesting Demand Box" if is_retesting else "⚪ Above Box",
                        "risk": round(risk, 2),
                        "target_2r": round(target_2r, 2),
                        "target_3r": round(target_3r, 2)
                    })

    return df, detected_zones


def run_full_screener(
    symbols: List[str],
    sw_len: int = 3,
    atr_mult: float = 1.2,
    buy_pct_thresh: float = 0.60,
    require_retest: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], Dict[str, List[dict]]]:
    """
    Executes the end-to-end scanner across selected symbol list.
    Returns:
    - Summary DataFrame of detected setups
    - Dictionary of symbol OHLCV dataframes
    - Dictionary of detected zones per symbol
    """
    raw_data = fetch_all_intraday_data(
        symbols=symbols,
        period="5d",
        interval="15m",
        chunk_size=50,
        max_workers=4,
        progress_callback=progress_callback
    )

    results_rows = []
    processed_dfs: Dict[str, pd.DataFrame] = {}
    symbol_zones: Dict[str, List[dict]] = {}

    for sym, df in raw_data.items():
        try:
            p_df, zones = calculate_bigbeluga_order_blocks(
                df,
                sw_len=sw_len,
                atr_mult=atr_mult,
                buy_pct_thresh=buy_pct_thresh
            )
            processed_dfs[sym] = p_df
            symbol_zones[sym] = zones

            if zones:
                latest_zone = zones[-1]
                if require_retest and not latest_zone["is_retesting"]:
                    continue

                display_sym = sym.replace(".NS", "")
                results_rows.append({
                    "Symbol": display_sym,
                    "Full Symbol": sym,
                    "Current Price (₹)": latest_zone["current_price"],
                    "Demand Box Range": latest_zone["box_range_str"],
                    "Box Bottom (₹)": latest_zone["bottom"],
                    "Box Top (₹)": latest_zone["top"],
                    "Buy Conviction (%)": latest_zone["buy_pct"],
                    "Relative Vol (RVOL)": latest_zone["rvol"],
                    "ATR (₹)": latest_zone["atr"],
                    "Displacement": latest_zone["displacement"],
                    "Disp / ATR": latest_zone["disp_atr_ratio"],
                    "Retesting": latest_zone["retest_status"],
                    "Is Retesting": latest_zone["is_retesting"],
                    "Formation Time": latest_zone["pivot_time"].strftime("%d %b %H:%M"),
                    "Total Active Zones": len(zones),
                    "2R Target (₹)": latest_zone["target_2r"]
                })
        except Exception as e:
            print(f"[run_full_screener] Error processing {sym}: {e}")

    summary_df = pd.DataFrame(results_rows)
    if not summary_df.empty:
        summary_df.sort_values(
            by=["Is Retesting", "Buy Conviction (%)", "Relative Vol (RVOL)"],
            ascending=[False, False, False],
            inplace=True
        )
        summary_df.reset_index(drop=True, inplace=True)

    return summary_df, processed_dfs, symbol_zones
