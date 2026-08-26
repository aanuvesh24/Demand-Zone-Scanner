# EasyMoney | NSE Institutional Demand Zone Scanner 📈

An institutional quantitative trading and screener web application built with **Streamlit** and **Plotly** to detect institutional Demand Zones (Bullish Order Blocks) across Indian National Stock Exchange (NSE) indices (**Nifty 50**, **Nifty 200**, **Nifty 500**) on a 15-minute timeframe using **BigBeluga's Volume-Weighted Order Block algorithm**.

---

## 🚀 Key Features

- **Automated NSE Constituent Ingestion**: Fetches live index constituents directly from NSE Archives with automated caching (`@st.cache_data(ttl=86400)`) and resilient fallback.
- **Concurrent Batch Fetching**: Parallelized intraday 15-minute data ingestion (`period="5d", interval="15m"`) in concurrent 50-ticker batches via `ThreadPoolExecutor` and direct Yahoo v8 chart API fallback.
- **BigBeluga Quantitative Engine**:
  - **14-Period ATR & True Range**: Dynamic volatility measurement.
  - **10-Period Volume SMA & RVOL**: Relative volume institutional benchmark.
  - **Intra-bar Buy Volume Ratio**: $\text{Buy\_Pct} = \frac{\text{Close} - \text{Low}}{\text{High} - \text{Low}}$.
  - **Swing Low Pivot Identification**: Configurable lookback ($sw\_len$).
  - **Displacement Check**: $\text{Close}_{next} - \text{Low}_{pivot} \ge \text{Multiplier} \times \text{ATR}$.
  - **Volume Conviction**: Institutional confirmation on pivot and breakout bars.
  - **Demand Zone Boundaries**: $\text{Bottom} = \text{Low}_{pivot}$, $\text{Top} = \max(\text{Open}_{pivot}, \text{Close}_{pivot})$.
  - **Active Retest Filter**: Detects active pullbacks into the demand zone ($\text{Bottom} \times 0.998 \le \text{Price} \le \text{Top} \times 1.005$).
- **Interactive Dark Dashboard**:
  - Glassmorphic KPI cards for instant market summary.
  - Interactive, sortable, and downloadable screener table.
  - 2-row dark Plotly subplot with 15m candlesticks, green shaded demand boxes, 2R/3R targets, and volume with 10-SMA line.

---

## 🛠️ Tech Stack

- **Frontend / Framework**: `streamlit`, `plotly` (with `plotly.subplots`)
- **Data & Computation**: `yfinance`, `pandas`, `numpy`, `requests`
- **Concurrency**: Python `concurrent.futures.ThreadPoolExecutor`

---

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aanuvesh24/easymoney.git
   cd easymoney
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the application:**
   ```bash
   streamlit run app.py
   ```
   Open `http://localhost:8501` in your browser.

---

## 📄 License
Private & Proprietary. All rights reserved.
