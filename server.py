"""
EasyMoney - High-Performance FastAPI Backend
Quantitative Institutional Demand Zone Scanner Engine API
"""

import os
import io
import csv
import json
import time
import asyncio
import datetime
import pytz
from typing import Optional, Dict, List, Any
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine import (
    fetch_nse_symbols,
    run_full_screener,
    calculate_bigbeluga_order_blocks,
    fetch_single_ticker_direct,
    format_ticker_chart_payload,
    FALLBACK_TOP25_NSE,
    NSE_ARCHIVE_URLS
)

app = FastAPI(
    title="EasyMoney Quant API",
    description="Institutional 15-Minute Demand Zone (Order Block) Scanner API",
    version="2.0.0"
)

# Enable CORS for maximum flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State Container
class ScreenerState:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.is_scanning = False
        self.last_scan_time: Optional[datetime.datetime] = None
        self.universe: str = "Nifty 50"
        self.params: dict = {
            "sw_len": 3,
            "atr_mult": 1.2,
            "buy_pct_thresh": 0.60,
            "require_retest": False
        }
        self.progress: int = 0
        self.current_count: int = 0
        self.total_count: int = 0
        self.status_message: str = "Ready"
        self.summary_df = None
        self.processed_dfs: Dict[str, Any] = {}
        self.symbol_zones: Dict[str, List[dict]] = {}
        self.subscribers: List[asyncio.Queue] = []

    def get_metrics(self) -> dict:
        total_scanned = len(self.processed_dfs) if self.processed_dfs else 0
        if self.summary_df is not None and not self.summary_df.empty:
            total_detected = len(self.summary_df)
            retesting_count = int(self.summary_df["Is Retesting"].sum()) if "Is Retesting" in self.summary_df.columns else 0
            avg_conviction = round(float(self.summary_df["Buy Conviction (%)"].mean()), 1) if "Buy Conviction (%)" in self.summary_df.columns else 0.0
            top_ticker = str(self.summary_df.iloc[0]["Symbol"]) if len(self.summary_df) > 0 else "-"
        else:
            total_detected = 0
            retesting_count = 0
            avg_conviction = 0.0
            top_ticker = "-"

        ist_tz = pytz.timezone("Asia/Kolkata")
        last_updated_str = self.last_scan_time.astimezone(ist_tz).strftime("%d %b %Y, %I:%M:%S %p IST") if self.last_scan_time else "Never"

        return {
            "universe": self.universe,
            "total_scanned": total_scanned,
            "demand_zones_detected": total_detected,
            "retesting_count": retesting_count,
            "avg_buy_conviction": avg_conviction,
            "top_opportunity": top_ticker,
            "last_updated": last_updated_str,
            "is_scanning": self.is_scanning,
            "progress": self.progress,
            "status_message": self.status_message
        }

    async def broadcast_progress(self, progress: int, current: int, total: int, msg: str, is_scanning: bool = True):
        self.progress = progress
        self.current_count = current
        self.total_count = total
        self.status_message = msg
        self.is_scanning = is_scanning
        data = {
            "progress": progress,
            "current": current,
            "total": total,
            "message": msg,
            "is_scanning": is_scanning
        }
        for q in list(self.subscribers):
            try:
                await q.put(data)
            except Exception:
                pass


state = ScreenerState()


class ScanRequest(BaseModel):
    universe: str = Field(default="Nifty 50", description="NSE Universe: Nifty 50, Nifty 200, Nifty 500")
    buy_conviction_pct: int = Field(default=60, ge=50, le=90, description="Minimum Buy Volume Conviction %")
    atr_mult: float = Field(default=1.2, ge=0.8, le=3.0, description="ATR displacement multiplier")
    sw_len: int = Field(default=3, ge=2, le=7, description="Swing Pivot Lookback length")
    require_retest: bool = Field(default=False, description="Filter only setups sitting in/near demand box")


# Background scan task
def execute_background_scan(universe: str, sw_len: int, atr_mult: float, buy_pct_thresh: float, require_retest: bool, loop: asyncio.AbstractEventLoop):
    try:
        symbols = fetch_nse_symbols(universe)
        total_syms = len(symbols)

        def sync_progress(cur, tot, msg):
            pct = int((cur / max(1, tot)) * 100)
            asyncio.run_coroutine_threadsafe(
                state.broadcast_progress(pct, cur, tot, msg, is_scanning=True),
                loop
            )

        summary_df, processed_dfs, symbol_zones = run_full_screener(
            symbols=symbols,
            sw_len=sw_len,
            atr_mult=atr_mult,
            buy_pct_thresh=buy_pct_thresh,
            require_retest=require_retest,
            progress_callback=sync_progress
        )

        state.summary_df = summary_df
        state.processed_dfs = processed_dfs
        state.symbol_zones = symbol_zones
        state.universe = universe
        state.last_scan_time = datetime.datetime.now(datetime.timezone.utc)
        state.is_scanning = False

        asyncio.run_coroutine_threadsafe(
            state.broadcast_progress(100, total_syms, total_syms, f"Scan complete! Found {len(summary_df)} active setups.", is_scanning=False),
            loop
        )
    except Exception as e:
        print(f"[execute_background_scan] Error: {e}")
        state.is_scanning = False
        asyncio.run_coroutine_threadsafe(
            state.broadcast_progress(0, 0, 0, f"Scan failed: {str(e)}", is_scanning=False),
            loop
        )


@app.get("/api/universes")
async def get_universes():
    """Returns available NSE constituent universes."""
    return {
        "universes": [
            {"id": "Nifty 50", "name": "Nifty 50", "description": "Top 50 Mega-Cap Liquid NSE Leaders", "default": True},
            {"id": "Nifty 200", "name": "Nifty 200", "description": "Large & Mid-Cap Institutional Universe (200 Stocks)", "default": False},
            {"id": "Nifty 500", "name": "Nifty 500", "description": "Broad Market Comprehensive Screener (500 Stocks)", "default": False},
        ]
    }


@app.post("/api/scan")
async def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Triggers an institutional quantitative scan across the selected universe."""
    if state.is_scanning:
        return JSONResponse(
            status_code=409,
            content={"message": "A scan is already in progress. Please wait for completion.", "status": "busy"}
        )

    state.is_scanning = True
    state.progress = 0
    state.universe = req.universe
    state.params = {
        "sw_len": req.sw_len,
        "atr_mult": req.atr_mult,
        "buy_pct_thresh": req.buy_conviction_pct / 100.0,
        "require_retest": req.require_retest
    }

    loop = asyncio.get_running_loop()
    background_tasks.add_task(
        execute_background_scan,
        universe=req.universe,
        sw_len=req.sw_len,
        atr_mult=req.atr_mult,
        buy_pct_thresh=req.buy_conviction_pct / 100.0,
        require_retest=req.require_retest,
        loop=loop
    )

    return {
        "status": "started",
        "message": f"Initiated institutional scan for {req.universe}...",
        "universe": req.universe,
        "params": state.params
    }


@app.get("/api/scan/progress")
async def stream_progress():
    """Server-Sent Events (SSE) endpoint for real-time scan progress broadcasting."""
    queue = asyncio.Queue()
    state.subscribers.append(queue)

    # Initial state push
    await queue.put({
        "progress": state.progress,
        "current": state.current_count,
        "total": state.total_count,
        "message": state.status_message,
        "is_scanning": state.is_scanning
    })

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in state.subscribers:
                state.subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/results")
async def get_screener_results():
    """Returns current screener results, KPI metrics, and table records."""
    metrics = state.get_metrics()
    results_list = []
    
    if state.summary_df is not None and not state.summary_df.empty:
        # Convert df to dictionary records
        for _, row in state.summary_df.iterrows():
            results_list.append({
                "symbol": str(row["Symbol"]),
                "full_symbol": str(row["Full Symbol"]),
                "current_price": float(row["Current Price (₹)"]),
                "demand_box_range": str(row["Demand Box Range"]),
                "box_bottom": float(row["Box Bottom (₹)"]),
                "box_top": float(row["Box Top (₹)"]),
                "buy_conviction": float(row["Buy Conviction (%)"]),
                "rvol": float(row["Relative Vol (RVOL)"]),
                "atr": float(row["ATR (₹)"]),
                "displacement": float(row["Displacement"]),
                "disp_atr_ratio": float(row["Disp / ATR"]),
                "retesting_status": str(row["Retesting"]),
                "is_retesting": bool(row["Is Retesting"]),
                "formation_time": str(row["Formation Time"]),
                "total_zones": int(row["Total Active Zones"]),
                "target_2r": float(row["2R Target (₹)"])
            })

    # Available symbols list for dropdown
    available_symbols = []
    if results_list:
        available_symbols = [r["full_symbol"] for r in results_list]
    elif state.processed_dfs:
        available_symbols = list(state.processed_dfs.keys())
    else:
        available_symbols = FALLBACK_TOP25_NSE

    return {
        "metrics": metrics,
        "count": len(results_list),
        "results": results_list,
        "available_symbols": available_symbols,
        "params": state.params
    }


@app.get("/api/ticker/{symbol}")
async def get_ticker_data(symbol: str, sw_len: Optional[int] = None, atr_mult: Optional[float] = None, buy_pct_thresh: Optional[float] = None):
    """Fetches intraday 15m candle chart data and calculated BigBeluga Order Blocks for a given ticker."""
    clean_sym = symbol.strip().upper()
    if not clean_sym.endswith(".NS"):
        clean_sym += ".NS"

    s_len = sw_len if sw_len is not None else state.params.get("sw_len", 3)
    a_mult = atr_mult if atr_mult is not None else state.params.get("atr_mult", 1.2)
    b_thresh = buy_pct_thresh if buy_pct_thresh is not None else state.params.get("buy_pct_thresh", 0.60)

    # Check if already processed in memory
    df = state.processed_dfs.get(clean_sym)
    zones = state.symbol_zones.get(clean_sym, [])

    # If missing or custom parameters requested, fetch direct data
    if df is None:
        raw_df = fetch_single_ticker_direct(clean_sym, period="5d", interval="15m")
        if raw_df is None or raw_df.empty:
            raise HTTPException(status_code=404, detail=f"Data for ticker {clean_sym} could not be retrieved.")
        df, zones = calculate_bigbeluga_order_blocks(
            raw_df,
            sw_len=s_len,
            atr_mult=a_mult,
            buy_pct_thresh=b_thresh
        )
        state.processed_dfs[clean_sym] = df
        state.symbol_zones[clean_sym] = zones

    payload = format_ticker_chart_payload(clean_sym, df, zones)
    return payload


@app.get("/api/export")
async def export_screener_csv():
    """Generates and downloads a CSV export of current screener findings."""
    if state.summary_df is None or state.summary_df.empty:
        raise HTTPException(status_code=400, detail="No screener results available to export. Please run a scan first.")

    output = io.StringIO()
    state.summary_df.to_csv(output, index=False)
    output.seek(0)
    
    date_str = datetime.date.today().strftime("%Y%m%d")
    filename = f"easymoney_order_blocks_{state.universe.lower().replace(' ', '_')}_{date_str}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "EasyMoney Quant Engine",
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


# Ensure static directory exists and mount it
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the modern frontend Single Page Application."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>EasyMoney Frontend loading...</h1>", status_code=200)


# Pre-seed initial scan on startup in background
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    # Trigger initial fast scan in background thread so app is ready immediately
    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(
        execute_background_scan,
        universe="Nifty 50",
        sw_len=3,
        atr_mult=1.2,
        buy_pct_thresh=0.60,
        require_retest=False,
        loop=loop
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
