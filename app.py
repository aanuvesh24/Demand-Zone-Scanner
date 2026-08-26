"""
EasyMoney - NSE 15-Minute Institutional Demand Zone (Order Block) Scanner
Powered by BigBeluga's Volume-Weighted Order Block Algorithm
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import pytz

from engine import (
    fetch_nse_symbols,
    run_full_screener,
    calculate_bigbeluga_order_blocks,
    fetch_single_ticker_direct,
    FALLBACK_TOP25_NSE,
    NSE_ARCHIVE_URLS
)

# Set Page Config
st.set_page_config(
    page_title="EasyMoney | NSE Demand Zone Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-Aesthetic Styling
st.markdown("""
<style>
    /* Dark Modern Theme Styling */
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Metric Card Styling */
    .metric-card {
        background: linear-gradient(135deg, rgba(22, 27, 34, 0.8) 0%, rgba(33, 38, 45, 0.8) 100%);
        border: 1px solid rgba(48, 54, 61, 0.8);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #00e676;
    }
    .metric-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
        display: flex;
        align-items: baseline;
        gap: 6px;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #00e676;
        font-weight: 500;
    }

    /* Section Headers */
    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #f0f6fc;
        margin-top: 24px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Glow Badges */
    .badge-retest {
        background-color: rgba(0, 230, 118, 0.15);
        color: #00e676;
        border: 1px solid rgba(0, 230, 118, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .badge-above {
        background-color: rgba(56, 139, 253, 0.15);
        color: #58a6ff;
        border: 1px solid rgba(56, 139, 253, 0.4);
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Setup info box */
    .setup-box {
        background: rgba(13, 23, 18, 0.85);
        border: 1px solid rgba(0, 230, 118, 0.3);
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 16px;
    }

    /* Hide Streamlit default branding padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)


# Cached constituent fetcher
@st.cache_data(ttl=86400, show_spinner=False)
def get_cached_nse_symbols(universe: str) -> list:
    return fetch_nse_symbols(universe)


def create_order_block_chart(symbol: str, df: pd.DataFrame, zones: list) -> go.Figure:
    """
    Creates an ultra-clean, dark-themed 2-row subplot chart with 15m Candlesticks,
    Volume bars, Volume SMA, Demand Zone boxes, and Risk-Reward projections.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28]
    )

    # 1. Candlestick Chart (Row 1)
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="15m Price",
            increasing_line_color="#00e676",
            increasing_fillcolor="#00e676",
            decreasing_line_color="#ff5252",
            decreasing_fillcolor="#ff5252",
            showlegend=False
        ),
        row=1, col=1
    )

    # 2. Volume Bars (Row 2)
    colors = np.where(df["Close"] >= df["Open"], "rgba(0, 230, 118, 0.75)", "rgba(255, 82, 82, 0.75)")
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Traded Volume",
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )

    # 3. Volume SMA 10 (Row 2)
    if "Vol_SMA" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Vol_SMA"],
                name="10-SMA Volume",
                line=dict(color="#ffd700", width=1.5),
                showlegend=True
            ),
            row=2, col=1
        )

    # 4. Render Shaded Demand Zone Boxes & Projections
    latest_bar_time = df.index[-1]
    
    for idx, z in enumerate(zones):
        p_time = z["pivot_time"]
        bottom = z["bottom"]
        top = z["top"]
        buy_pct = z["buy_pct"]
        is_latest = (idx == len(zones) - 1)
        
        # Shade color (brighter for latest active zone)
        fill_col = "rgba(0, 230, 118, 0.22)" if is_latest else "rgba(0, 230, 118, 0.10)"
        line_col = "rgba(0, 230, 118, 0.9)" if is_latest else "rgba(0, 230, 118, 0.4)"

        # Rectangular Demand Box Shape
        fig.add_shape(
            type="rect",
            x0=p_time,
            x1=latest_bar_time,
            y0=bottom,
            y1=top,
            fillcolor=fill_col,
            line=dict(color=line_col, width=1.5, dash="solid" if is_latest else "dot"),
            row=1, col=1
        )

        # Label annotation on demand zone box
        if is_latest:
            fig.add_annotation(
                x=p_time,
                y=top,
                text=f"🟢 <b>DEMAND ZONE</b> ({buy_pct:.0f}% Buy Vol)",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor="#00e676",
                ax=0,
                ay=-28,
                bgcolor="rgba(13, 23, 18, 0.9)",
                bordercolor="#00e676",
                borderwidth=1,
                borderpad=4,
                font=dict(color="#00e676", size=11),
                row=1, col=1
            )

            # Target 2R Projection Line
            if "target_2r" in z:
                fig.add_shape(
                    type="line",
                    x0=p_time,
                    x1=latest_bar_time,
                    y0=z["target_2r"],
                    y1=z["target_2r"],
                    line=dict(color="#58a6ff", width=1.2, dash="dash"),
                    row=1, col=1
                )
                fig.add_annotation(
                    x=latest_bar_time,
                    y=z["target_2r"],
                    text=f"🎯 Target 2R: ₹{z['target_2r']:.2f}",
                    showarrow=False,
                    xanchor="left",
                    font=dict(color="#58a6ff", size=10),
                    row=1, col=1
                )

            # Stop Loss (Bottom Invalidation) Line
            fig.add_shape(
                type="line",
                x0=p_time,
                x1=latest_bar_time,
                y0=bottom,
                y1=bottom,
                line=dict(color="#ff5252", width=1.2, dash="dot"),
                row=1, col=1
            )

    # Chart Layout & Dark Modern Styling
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol.replace('.NS', '')}</b> Intraday 15-Minute BigBeluga Demand Zone Inspector",
            font=dict(size=16, color="#f0f6fc")
        ),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        hovermode="x unified",
        dragmode="zoom",
        margin=dict(l=40, r=40, t=50, b=30),
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor="#21262d",
            showgrid=True,
            zeroline=False
        ),
        xaxis2=dict(
            gridcolor="#21262d",
            showgrid=True,
            zeroline=False
        ),
        yaxis=dict(
            title="Price (₹)",
            gridcolor="#21262d",
            showgrid=True,
            zeroline=False,
            side="right"
        ),
        yaxis2=dict(
            title="Volume",
            gridcolor="#21262d",
            showgrid=True,
            zeroline=False,
            side="right"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#8b949e", size=11),
            bgcolor="rgba(0,0,0,0)"
        ),
        height=620
    )

    return fig


# ---------------- SIDEBAR CONTROLS ----------------
with st.sidebar:
    st.markdown("### ⚡ EasyMoney Quant")
    st.markdown("<span style='color:#00e676; font-size:0.85rem; font-weight:600;'>Institutional Order Block Scanner</span>", unsafe_allow_html=True)
    st.markdown("---")

    # 1. Universe Selection
    universe = st.selectbox(
        "📊 Select Index Universe",
        options=["Nifty 50", "Nifty 200", "Nifty 500"],
        index=0,
        help="Select the NSE benchmark constituent universe to screen."
    )

    # Fetch symbols with caching
    symbols = get_cached_nse_symbols(universe)
    st.caption(f"Loaded **{len(symbols)}** constituents for {universe}")

    st.markdown("#### ⚙️ Quantitative Parameters")

    # 2. Buy Volume Conviction Slider
    buy_conviction_pct = st.slider(
        "💪 Min Buy Volume Conviction",
        min_value=50,
        max_value=90,
        value=60,
        step=5,
        format="%d%%",
        help="Intra-bar Buy Volume Ratio = (Close - Low) / (High - Low). Filters for high institutional accumulation."
    )
    buy_pct_thresh = buy_conviction_pct / 100.0

    # 3. ATR Displacement Multiplier Slider
    atr_mult = st.slider(
        "🚀 ATR Displacement Multiplier",
        min_value=0.8,
        max_value=2.5,
        value=1.2,
        step=0.1,
        format="%.1fx",
        help="Subsequent candle expansion required above swing low relative to 14-period ATR."
    )

    # 4. Swing Pivot Lookback Slider
    sw_len = st.slider(
        "🔍 Swing Pivot Lookback (`sw_len`)",
        min_value=2,
        max_value=7,
        value=3,
        step=1,
        help="Number of bars before and after to confirm a local Swing Low pivot."
    )

    # 5. Retest Filter Toggle
    require_retest = st.toggle(
        "🎯 Only Show Retesting Demand Boxes",
        value=False,
        help="Filter only for stocks whose current price is actively sitting inside or right above the demand box."
    )

    st.markdown("---")

    # Run Scanner Button
    scan_clicked = st.button("🚀 Run Institutional Scanner", type="primary", use_container_width=True)

    st.markdown("""
    <div style="margin-top: 20px; font-size: 0.78rem; color: #8b949e; background: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d;">
        <b>💡 BigBeluga Order Block Logic:</b><br/>
        • <b>Demand Box:</b> [Low, Max(Open,Close)] of swing pivot bar.<br/>
        • <b>Conviction:</b> Buy Vol Ratio ≥ Threshold + Volume ≥ 10-SMA.<br/>
        • <b>Displacement:</b> Upward thrust ≥ Multiplier × ATR.<br/>
        • <b>Retest Zone:</b> 0.998 × Bottom to 1.005 × Top.
    </div>
    """, unsafe_allow_html=True)


# ---------------- MAIN APPLICATION BODY ----------------

# App Header
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("<h2 style='margin-bottom:2px; color:#ffffff;'>Institutional Demand Zone Scanner</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8b949e; font-size:0.92rem;'>BigBeluga 15-Minute Volume-Weighted Order Block Engine for NSE Equities</p>", unsafe_allow_html=True)
with col_h2:
    ist_now = datetime.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d %b %Y | %H:%M IST")
    st.markdown(f"""
    <div style='text-align:right; margin-top:6px;'>
        <span class='badge-retest'>● Live NSE 15m</span><br/>
        <span style='color:#8b949e; font-size:0.78rem;'>{ist_now}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Session State Initialization for Scan Results
if "scan_results" not in st.session_state:
    st.session_state["scan_results"] = None
if "processed_dfs" not in st.session_state:
    st.session_state["processed_dfs"] = {}
if "symbol_zones" not in st.session_state:
    st.session_state["symbol_zones"] = {}
if "last_universe" not in st.session_state:
    st.session_state["last_universe"] = universe

# Auto-run initial scan if state is empty
if scan_clicked or st.session_state["scan_results"] is None or st.session_state["last_universe"] != universe:
    st.session_state["last_universe"] = universe
    
    progress_bar = st.progress(0, text="Initializing parallel data ingestion...")
    status_text = st.empty()

    def update_progress(current, total, msg):
        pct = int((current / max(1, total)) * 100)
        progress_bar.progress(pct, text=f"Scanning {universe} ({current}/{total}): {msg}")

    with st.spinner(f"Scanning {len(symbols)} tickers in {universe} on 15-minute timeframe..."):
        summary_df, processed_dfs, symbol_zones = run_full_screener(
            symbols=symbols,
            sw_len=sw_len,
            atr_mult=atr_mult,
            buy_pct_thresh=buy_pct_thresh,
            require_retest=require_retest,
            progress_callback=update_progress
        )

        st.session_state["scan_results"] = summary_df
        st.session_state["processed_dfs"] = processed_dfs
        st.session_state["symbol_zones"] = symbol_zones

    progress_bar.empty()
    status_text.empty()


# Display Summary Dashboard
results_df = st.session_state["scan_results"]
processed_dfs = st.session_state["processed_dfs"]
symbol_zones = st.session_state["symbol_zones"]

# Metric Cards
col_m1, col_m2, col_m3, col_m4 = st.columns(4)

total_scanned = len(processed_dfs) if processed_dfs else len(symbols)
total_detected = len(results_df) if results_df is not None else 0
retesting_count = int(results_df["Is Retesting"].sum()) if (results_df is not None and not results_df.empty) else 0
avg_conviction = f"{results_df['Buy Conviction (%)'].mean():.1f}%" if (results_df is not None and not results_df.empty) else "0.0%"

with col_m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Universe Scanned</div>
        <div class="metric-value">{total_scanned} <span style="font-size:1rem; color:#8b949e;">tickers</span></div>
        <div class="metric-sub">{universe} (15m)</div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Demand Zones Detected</div>
        <div class="metric-value" style="color:#00e676;">{total_detected}</div>
        <div class="metric-sub">Active Bullish Order Blocks</div>
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Retesting Box (Prime Entry)</div>
        <div class="metric-value" style="color:#ffd700;">{retesting_count}</div>
        <div class="metric-sub">At Demand Box Boundary</div>
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Avg Buy Conviction</div>
        <div class="metric-value" style="color:#58a6ff;">{avg_conviction}</div>
        <div class="metric-sub">Intra-bar Buy Volume Ratio</div>
    </div>
    """, unsafe_allow_html=True)


# ---------------- SCREENER RESULTS TABLE ----------------
st.markdown("<div class='section-title'>📋 Institutional Demand Zone Screener Results</div>", unsafe_allow_html=True)

if results_df is not None and not results_df.empty:
    display_cols = [
        "Symbol", "Current Price (₹)", "Demand Box Range", "Buy Conviction (%)",
        "Relative Vol (RVOL)", "ATR (₹)", "Displacement", "Retesting", "Formation Time", "2R Target (₹)"
    ]
    
    # Render interactive dataframe
    st.dataframe(
        results_df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Current Price (₹)": st.column_config.NumberColumn(format="₹%.2f"),
            "Buy Conviction (%)": st.column_config.ProgressColumn(
                format="%.1f%%",
                min_value=50,
                max_value=100
            ),
            "Relative Vol (RVOL)": st.column_config.NumberColumn(format="%.2fx"),
            "ATR (₹)": st.column_config.NumberColumn(format="₹%.2f"),
            "Displacement": st.column_config.NumberColumn(format="₹%.2f"),
            "2R Target (₹)": st.column_config.NumberColumn(format="₹%.2f")
        }
    )

    # Download CSV export
    csv_data = results_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Screener Results (CSV)",
        data=csv_data,
        file_name=f"nse_order_blocks_{universe.lower().replace(' ', '_')}_{datetime.date.today()}.csv",
        mime="text/csv"
    )
else:
    st.info(f"No active Demand Zones matched the current parameters in {universe}. Try lowering the Buy Conviction slider or ATR Displacement Multiplier.")


# ---------------- INTERACTIVE CHART INSPECTOR ----------------
st.markdown("<div class='section-title'>🔍 Interactive Chart & Order Block Inspector</div>", unsafe_allow_html=True)

# Select stock from results or universe
available_symbols = []
if results_df is not None and not results_df.empty:
    available_symbols = list(results_df["Full Symbol"].unique())
if not available_symbols and processed_dfs:
    available_symbols = list(processed_dfs.keys())
if not available_symbols:
    available_symbols = FALLBACK_TOP25_NSE

col_sel1, col_sel2 = st.columns([2, 2])
with col_sel1:
    selected_full_sym = st.selectbox(
        "Select Stock to Inspect",
        options=available_symbols,
        format_func=lambda s: s.replace(".NS", ""),
        index=0
    )

with col_sel2:
    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
    refresh_ticker_clicked = st.button("🔄 Refresh Ticker Data", use_container_width=False)

# Fetch or retrieve DataFrame for selected ticker
selected_df = None
selected_zones = []

if refresh_ticker_clicked or selected_full_sym not in processed_dfs:
    with st.spinner(f"Fetching live 15m data for {selected_full_sym}..."):
        single_df = fetch_single_ticker_direct(selected_full_sym, period="5d", interval="15m")
        if single_df is not None:
            p_df, z_list = calculate_bigbeluga_order_blocks(
                single_df,
                sw_len=sw_len,
                atr_mult=atr_mult,
                buy_pct_thresh=buy_pct_thresh
            )
            processed_dfs[selected_full_sym] = p_df
            symbol_zones[selected_full_sym] = z_list
            selected_df = p_df
            selected_zones = z_list
else:
    selected_df = processed_dfs.get(selected_full_sym)
    selected_zones = symbol_zones.get(selected_full_sym, [])

if selected_df is not None and not selected_df.empty:
    # Display Setup Breakdown Card if Zone Exists
    if selected_zones:
        latest_z = selected_zones[-1]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Demand Box Range", f"₹{latest_z['bottom']:.2f} - ₹{latest_z['top']:.2f}", f"Box Height: ₹{latest_z['box_height']:.2f}")
        c2.metric("Current Price", f"₹{latest_z['current_price']:.2f}", latest_z["retest_status"])
        c3.metric("Buy Conviction", f"{latest_z['buy_pct']:.1f}%", f"RVOL: {latest_z['rvol']:.2f}x")
        c4.metric("Displacement / ATR", f"{latest_z['displacement']:.2f} (₹)", f"{latest_z['disp_atr_ratio']:.1f}x ATR")
        c5.metric("Target 2R / 3R", f"₹{latest_z['target_2r']:.2f}", f"3R: ₹{latest_z['target_3r']:.2f}")

    # Render Plotly Chart
    fig = create_order_block_chart(selected_full_sym, selected_df, selected_zones)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning(f"Could not load intraday data for {selected_full_sym}. Please verify ticker availability.")
