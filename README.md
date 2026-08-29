# EasyMoney | NSE Institutional Demand Zone Scanner 📈

An institutional quantitative trading and screener web terminal built with **FastAPI** and a modern **Vanilla JS / CSS SPA** to detect institutional Demand Zones (Bullish Order Blocks) across Indian National Stock Exchange (NSE) indices (**Nifty 50**, **Nifty 200**, **Nifty 500**) on a 15-minute timeframe using **BigBeluga's Volume-Weighted Order Block algorithm**.

---

## 🚀 Key Features

- **Automated NSE Constituent Ingestion**: Fetches live index constituents directly from NSE Archives with automated caching and resilient fallback.
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
- **Modern Institutional Web Terminal**:
  - Cyber-slate dark theme with glassmorphic cards and live glowing status badges.
  - Real-time Server-Sent Events (SSE) live progress bar and scan status broadcast.
  - Interactive, sortable, and downloadable screener data grid with quick filter chips.
  - Pro 2-row candlestick & volume chart inspector with green shaded demand boxes, 2R/3R targets, and 10-period SMA line.

---

## 🛠️ Tech Stack

- **Backend**: `FastAPI`, `Uvicorn`, `requests`
- **Frontend**: Modern HTML5, Vanilla CSS3 (Custom Design System), JavaScript (ES6+), `Plotly.js`
- **Data & Computation**: `yfinance`, `pandas`, `numpy`
- **Concurrency**: Python `concurrent.futures.ThreadPoolExecutor`, `asyncio` SSE

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
   python3 server.py
   ```
   or with uvicorn:
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000 --reload
   ```
   Open `http://localhost:8000` in your browser.

---

## 📄 License
Private & Proprietary. All rights reserved.

