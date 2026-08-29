/**
 * EasyMoney - Institutional Quant Frontend Application
 * BigBeluga 15-Minute Volume-Weighted Order Block Screener & Inspector
 * Kinetic Typography Design System
 */

(function () {
  'use strict';

  // Global State
  const state = {
    universe: 'Nifty 50',
    buyConvictionPct: 60,
    atrMult: 1.2,
    swLen: 3,
    requireRetest: false,
    screenerResults: [],
    availableSymbols: [],
    activeSymbol: null,
    currentFilter: 'all',
    searchQuery: '',
    sortColumn: 'is_retesting',
    sortAsc: false,
    isScanning: false,
    eventSource: null,
    chartData: null
  };

  // DOM Elements
  const elements = {
    liveClock: document.getElementById('liveClock'),
    universeTabs: document.getElementById('universeTabs'),
    startScanBtn: document.getElementById('startScanBtn'),
    scanBtnText: document.getElementById('scanBtnText'),
    scanBtnIcon: document.getElementById('scanBtnIcon'),
    scanProgressBarContainer: document.getElementById('scanProgressBarContainer'),
    scanProgressBar: document.getElementById('scanProgressBar'),
    scanStatusStrip: document.getElementById('scanStatusStrip'),
    scanStatusMessage: document.getElementById('scanStatusMessage'),
    scanCountRatio: document.getElementById('scanCountRatio'),
    scanPercentBadge: document.getElementById('scanPercentBadge'),
    kineticMarqueeTrack: document.getElementById('kineticMarqueeTrack'),
    
    // KPI
    kpiScannedCount: document.getElementById('kpiScannedCount'),
    kpiUniverseLabel: document.getElementById('kpiUniverseLabel'),
    kpiZonesCount: document.getElementById('kpiZonesCount'),
    kpiRetestCount: document.getElementById('kpiRetestCount'),
    kpiAvgConviction: document.getElementById('kpiAvgConviction'),

    // Quant Controls
    toggleControlsBtn: document.getElementById('toggleControlsBtn'),
    toggleControlsText: document.getElementById('toggleControlsText'),
    toggleControlsIcon: document.getElementById('toggleControlsIcon'),
    controlsBody: document.getElementById('controlsBody'),
    sliderBuyConviction: document.getElementById('sliderBuyConviction'),
    valBuyConviction: document.getElementById('valBuyConviction'),
    sliderAtrMult: document.getElementById('sliderAtrMult'),
    valAtrMult: document.getElementById('valAtrMult'),
    sliderSwLen: document.getElementById('sliderSwLen'),
    valSwLen: document.getElementById('valSwLen'),
    toggleRetestOnly: document.getElementById('toggleRetestOnly'),

    // Screener Matrix
    resultsCountPill: document.getElementById('resultsCountPill'),
    symbolSearchInput: document.getElementById('symbolSearchInput'),
    clearSearchBtn: document.getElementById('clearSearchBtn'),
    screenerTable: document.getElementById('screenerTable'),
    screenerTableBody: document.getElementById('screenerTableBody'),
    tableSummaryText: document.getElementById('tableSummaryText'),
    lastUpdatedTime: document.getElementById('lastUpdatedTime'),

    // Inspector
    activeSymbolBadge: document.getElementById('activeSymbolBadge'),
    activePrice: document.getElementById('activePrice'),
    activeChange: document.getElementById('activeChange'),
    stockSelectorDropdown: document.getElementById('stockSelectorDropdown'),
    refreshTickerBtn: document.getElementById('refreshTickerBtn'),
    refreshIcon: document.getElementById('refreshIcon'),
    
    // HUD
    hudBoxRange: document.getElementById('hudBoxRange'),
    hudBoxHeight: document.getElementById('hudBoxHeight'),
    hudRetestStatus: document.getElementById('hudRetestStatus'),
    hudFormationTime: document.getElementById('hudFormationTime'),
    hudConviction: document.getElementById('hudConviction'),
    hudRvol: document.getElementById('hudRvol'),
    hudDisplacement: document.getElementById('hudDisplacement'),
    hudDispAtr: document.getElementById('hudDispAtr'),
    hudTarget2r: document.getElementById('hudTarget2r'),
    hudTarget3r: document.getElementById('hudTarget3r'),
    plotlyChartContainer: document.getElementById('plotlyChartContainer'),

    // Strategy Modal & Export
    algoInfoBtn: document.getElementById('algoInfoBtn'),
    exportCsvBtn: document.getElementById('exportCsvBtn'),
    algoModal: document.getElementById('algoModal'),
    closeModalBtn: document.getElementById('closeModalBtn'),
    modalGotItBtn: document.getElementById('modalGotItBtn'),
    toastContainer: document.getElementById('toastContainer')
  };

  /* ==========================================================================
     INIT & EVENT LISTENERS
     ========================================================================== */
  function init() {
    startLiveClock();
    setupEventListeners();
    initSSEProgressStream();
    fetchScreenerResults();
  }

  function startLiveClock() {
    function updateClock() {
      const options = { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
      const istString = new Intl.DateTimeFormat('en-IN', options).format(new Date());
      if (elements.liveClock) {
        elements.liveClock.textContent = `${istString} IST`;
      }
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  function setupEventListeners() {
    // Universe Tabs
    if (elements.universeTabs) {
      elements.universeTabs.addEventListener('click', (e) => {
        const tab = e.target.closest('.univ-tab');
        if (!tab || tab.classList.contains('active')) return;
        
        document.querySelectorAll('.univ-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.universe = tab.dataset.universe;
        showToast(`Selected universe: ${state.universe}`, 'info');
        triggerScan();
      });
    }

    // Scan Trigger Button
    if (elements.startScanBtn) {
      elements.startScanBtn.addEventListener('click', () => {
        triggerScan();
      });
    }

    // Toggle Controls Panel
    if (elements.toggleControlsBtn) {
      elements.toggleControlsBtn.addEventListener('click', () => {
        const isCollapsed = elements.controlsBody.classList.toggle('hidden');
        elements.toggleControlsText.textContent = isCollapsed ? 'SHOW PARAMETERS' : 'HIDE PARAMETERS';
        elements.toggleControlsIcon.className = isCollapsed ? 'fa-solid fa-chevron-down' : 'fa-solid fa-chevron-up';
      });
    }

    // Range Sliders
    elements.sliderBuyConviction.addEventListener('input', (e) => {
      state.buyConvictionPct = parseInt(e.target.value, 10);
      elements.valBuyConviction.textContent = `${state.buyConvictionPct}%`;
    });

    elements.sliderAtrMult.addEventListener('input', (e) => {
      state.atrMult = parseFloat(e.target.value);
      elements.valAtrMult.textContent = `${state.atrMult.toFixed(1)}x`;
    });

    elements.sliderSwLen.addEventListener('input', (e) => {
      state.swLen = parseInt(e.target.value, 10);
      elements.valSwLen.textContent = `${state.swLen} BARS`;
    });

    elements.toggleRetestOnly.addEventListener('change', (e) => {
      state.requireRetest = e.target.checked;
      filterAndRenderTable();
    });

    // Preset Filter Chips
    document.querySelectorAll('.filter-chips-row .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.filter-chips-row .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        state.currentFilter = chip.dataset.filter;
        filterAndRenderTable();
      });
    });

    // Search Input
    elements.symbolSearchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.trim().toUpperCase();
      elements.clearSearchBtn.classList.toggle('hidden', state.searchQuery.length === 0);
      filterAndRenderTable();
    });

    elements.clearSearchBtn.addEventListener('click', () => {
      elements.symbolSearchInput.value = '';
      state.searchQuery = '';
      elements.clearSearchBtn.classList.add('hidden');
      filterAndRenderTable();
    });

    // Table Header Sorting
    elements.screenerTable.querySelectorAll('th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.sort;
        if (state.sortColumn === col) {
          state.sortAsc = !state.sortAsc;
        } else {
          state.sortColumn = col;
          state.sortAsc = false;
        }
        filterAndRenderTable();
      });
    });

    // Stock Selector Dropdown
    elements.stockSelectorDropdown.addEventListener('change', (e) => {
      const sym = e.target.value;
      if (sym) {
        loadTickerChart(sym);
      }
    });

    // Refresh Ticker Button
    elements.refreshTickerBtn.addEventListener('click', () => {
      if (state.activeSymbol) {
        elements.refreshIcon.classList.add('fa-spin');
        loadTickerChart(state.activeSymbol, true);
      }
    });

    // Export CSV
    elements.exportCsvBtn.addEventListener('click', () => {
      window.location.href = '/api/export';
      showToast('Exporting screener results to CSV...', 'info');
    });

    // Strategy Modal
    elements.algoInfoBtn.addEventListener('click', () => {
      elements.algoModal.classList.remove('hidden');
    });
    elements.closeModalBtn.addEventListener('click', () => {
      elements.algoModal.classList.add('hidden');
    });
    elements.modalGotItBtn.addEventListener('click', () => {
      elements.algoModal.classList.add('hidden');
    });
    elements.algoModal.addEventListener('click', (e) => {
      if (e.target === elements.algoModal) {
        elements.algoModal.classList.add('hidden');
      }
    });

    // Window Resize Chart Fix
    window.addEventListener('resize', () => {
      if (window.Plotly && elements.plotlyChartContainer) {
        Plotly.Plots.resize(elements.plotlyChartContainer);
      }
    });
  }

  /* ==========================================================================
     SSE PROGRESS STREAMING
     ========================================================================== */
  function initSSEProgressStream() {
    if (state.eventSource) {
      state.eventSource.close();
    }

    try {
      state.eventSource = new EventSource('/api/scan/progress');
      
      state.eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleProgressUpdate(data);
      };

      state.eventSource.onerror = () => {
        // SSE disconnected, will retry automatically
      };
    } catch (err) {
      console.warn('[SSE] Connection error:', err);
    }
  }

  function handleProgressUpdate(data) {
    const { progress, current, total, message, is_scanning } = data;

    state.isScanning = is_scanning;

    if (is_scanning) {
      elements.scanProgressBarContainer.classList.remove('hidden');
      elements.scanStatusStrip.classList.remove('hidden');
      elements.scanProgressBar.style.width = `${progress}%`;
      elements.scanStatusMessage.textContent = (message || 'SCANNING CONSTITUENTS...').toUpperCase();
      elements.scanCountRatio.textContent = `${current} / ${total}`;
      elements.scanPercentBadge.textContent = `${progress}%`;

      elements.startScanBtn.disabled = true;
      elements.scanBtnIcon.className = 'fa-solid fa-spinner fa-spin';
      elements.scanBtnText.textContent = `SCANNING (${progress}%)...`;
    } else {
      elements.scanProgressBar.style.width = '100%';
      setTimeout(() => {
        elements.scanProgressBarContainer.classList.add('hidden');
        elements.scanStatusStrip.classList.add('hidden');
      }, 800);

      elements.startScanBtn.disabled = false;
      elements.scanBtnIcon.className = 'fa-solid fa-radar';
      elements.scanBtnText.textContent = 'RUN INSTITUTIONAL SCAN';

      // If progress just completed to 100%, refresh results
      if (progress === 100) {
        fetchScreenerResults();
        showToast(message || 'Scan completed successfully!', 'success');
      }
    }
  }

  /* ==========================================================================
     API ACTIONS
     ========================================================================== */
  async function triggerScan() {
    if (state.isScanning) return;

    try {
      elements.startScanBtn.disabled = true;
      elements.scanBtnIcon.className = 'fa-solid fa-spinner fa-spin';
      elements.scanBtnText.textContent = 'INITIALIZING...';

      const payload = {
        universe: state.universe,
        buy_conviction_pct: state.buyConvictionPct,
        atr_mult: state.atrMult,
        sw_len: state.swLen,
        require_retest: state.requireRetest
      };

      const resp = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const res = await resp.json();
      if (!resp.ok) {
        showToast(res.message || 'Scan request failed', 'warning');
        elements.startScanBtn.disabled = false;
        elements.scanBtnIcon.className = 'fa-solid fa-radar';
        elements.scanBtnText.textContent = 'RUN INSTITUTIONAL SCAN';
      } else {
        showToast(`Scan initiated for ${state.universe}`, 'info');
      }
    } catch (err) {
      console.error('[triggerScan] Error:', err);
      showToast('Failed to trigger scan. Check server connection.', 'warning');
      elements.startScanBtn.disabled = false;
      elements.scanBtnIcon.className = 'fa-solid fa-radar';
      elements.scanBtnText.textContent = 'RUN INSTITUTIONAL SCAN';
    }
  }

  async function fetchScreenerResults() {
    try {
      const resp = await fetch('/api/results');
      if (!resp.ok) return;

      const data = await resp.json();
      state.screenerResults = data.results || [];
      state.availableSymbols = data.available_symbols || [];

      updateKpiCards(data.metrics);
      updateLiveMarquee(state.screenerResults);
      populateStockDropdown(state.availableSymbols);
      filterAndRenderTable();

      // Automatically select and render first ticker if not already set
      if (!state.activeSymbol && state.screenerResults.length > 0) {
        loadTickerChart(state.screenerResults[0].full_symbol);
      } else if (!state.activeSymbol && state.availableSymbols.length > 0) {
        loadTickerChart(state.availableSymbols[0]);
      }
    } catch (err) {
      console.error('[fetchScreenerResults] Error:', err);
    }
  }

  function updateKpiCards(metrics) {
    if (!metrics) return;
    elements.kpiScannedCount.innerHTML = `${metrics.total_scanned} <span class="kpi-unit">TICKERS</span>`;
    elements.kpiUniverseLabel.textContent = `${metrics.universe.toUpperCase()} • 15M TIMEFRAME`;
    elements.kpiZonesCount.textContent = metrics.demand_zones_detected;
    elements.kpiRetestCount.textContent = metrics.retesting_count;
    elements.kpiAvgConviction.textContent = `${metrics.avg_buy_conviction}%`;
    elements.lastUpdatedTime.textContent = `LAST SCAN: ${metrics.last_updated.toUpperCase()}`;
  }

  /* ==========================================================================
     DYNAMIC KINETIC MARQUEE GENERATOR
     ========================================================================== */
  function updateLiveMarquee(results) {
    if (!elements.kineticMarqueeTrack) return;

    if (!results || results.length === 0) {
      // Default institutional strategy ticker
      elements.kineticMarqueeTrack.innerHTML = `
        <div class="marquee-item"><span class="pulse-neon"></span><span>MARKET: <strong>NSE 15M INTRADAY</strong></span></div>
        <div class="marquee-item"><span>STRATEGY: <span class="marquee-badge">BIGBELUGA ORDER BLOCKS</span></span></div>
        <div class="marquee-item"><span>DISPLACEMENT: <strong>≥ 1.2x 14-ATR</strong></span></div>
        <div class="marquee-item"><span>CONVICTION: <strong>≥ 60% BUY VOLUME</strong></span></div>
        <div class="marquee-item"><span class="pulse-neon"></span><span>MARKET: <strong>NSE 15M INTRADAY</strong></span></div>
        <div class="marquee-item"><span>STRATEGY: <span class="marquee-badge">BIGBELUGA ORDER BLOCKS</span></span></div>
        <div class="marquee-item"><span>DISPLACEMENT: <strong>≥ 1.2x 14-ATR</strong></span></div>
        <div class="marquee-item"><span>CONVICTION: <strong>≥ 60% BUY VOLUME</strong></span></div>
      `;
      return;
    }

    let itemsHtml = '';
    results.slice(0, 15).forEach(row => {
      const retestBadge = row.is_retesting ? `<span class="marquee-badge">PRIME RETEST</span>` : '';
      itemsHtml += `
        <div class="marquee-item">
          <span class="pulse-neon"></span>
          <strong>${row.symbol}</strong>
          <span>₹${row.current_price.toFixed(2)}</span>
          ${retestBadge}
          <span>BUY CONV: <span class="text-accent">${row.buy_conviction.toFixed(0)}%</span></span>
          <span>RVOL: <strong>${row.rvol.toFixed(2)}x</strong></span>
        </div>
      `;
    });

    // Duplicate content to maintain seamless 100% infinite translation loop
    elements.kineticMarqueeTrack.innerHTML = itemsHtml + itemsHtml;
  }

  function populateStockDropdown(symbols) {
    if (!elements.stockSelectorDropdown) return;
    elements.stockSelectorDropdown.innerHTML = '';
    
    symbols.forEach(sym => {
      const opt = document.createElement('option');
      opt.value = sym;
      opt.textContent = sym.replace('.NS', '');
      elements.stockSelectorDropdown.appendChild(opt);
    });

    if (state.activeSymbol) {
      elements.stockSelectorDropdown.value = state.activeSymbol;
    }
  }

  /* ==========================================================================
     SCREENER TABLE RENDERING & FILTERING
     ========================================================================== */
  function filterAndRenderTable() {
    let list = [...state.screenerResults];

    // Filter by Preset Chips
    if (state.currentFilter === 'retest') {
      list = list.filter(item => item.is_retesting);
    } else if (state.currentFilter === 'high-conviction') {
      list = list.filter(item => item.buy_conviction >= 75);
    } else if (state.currentFilter === 'high-rvol') {
      list = list.filter(item => item.rvol >= 1.5);
    }

    // Filter by Toggle
    if (state.requireRetest) {
      list = list.filter(item => item.is_retesting);
    }

    // Search Query Filter
    if (state.searchQuery) {
      list = list.filter(item => 
        item.symbol.toUpperCase().includes(state.searchQuery) ||
        item.full_symbol.toUpperCase().includes(state.searchQuery)
      );
    }

    // Sorting
    list.sort((a, b) => {
      let valA = a[state.sortColumn];
      let valB = b[state.sortColumn];
      if (typeof valA === 'string') {
        return state.sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return state.sortAsc ? (valA - valB) : (valB - valA);
    });

    elements.resultsCountPill.textContent = `${list.length} SETUPS`;
    elements.tableSummaryText.textContent = `SHOWING ${list.length} OF ${state.screenerResults.length} DETECTED SETUPS`;

    if (list.length === 0) {
      elements.screenerTableBody.innerHTML = `
        <tr>
          <td colspan="9" class="table-loading-row">
            <div style="padding: 32px; color: #A1A1AA; font-family: var(--font-mono); text-transform: uppercase;">
              <i class="fa-solid fa-radar" style="font-size: 2.2rem; color: #3F3F46; margin-bottom: 12px; display: block;"></i>
              <p>NO DEMAND ZONE SETUPS MATCH CURRENT FILTERS IN ${state.universe.toUpperCase()}.</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    let html = '';
    list.forEach(row => {
      const isActive = (state.activeSymbol === row.full_symbol);
      const isRetest = row.is_retesting;
      const statusBadge = isRetest 
        ? `<span class="retest-badge"><i class="fa-solid fa-bullseye"></i> RETESTING</span>`
        : `<span class="retest-badge pending">ABOVE ZONE</span>`;

      html += `
        <tr class="${isActive ? 'active-row' : ''}" data-symbol="${row.full_symbol}">
          <td>
            <span class="stock-symbol-badge">${row.symbol}</span>
          </td>
          <td style="font-weight: 700;">₹${row.current_price.toFixed(2)}</td>
          <td>${row.demand_box_range}</td>
          <td>
            <span style="color: var(--accent); font-weight: 800;">${row.buy_conviction.toFixed(0)}%</span>
          </td>
          <td><strong>${row.rvol.toFixed(2)}x</strong></td>
          <td>${row.disp_atr_ratio.toFixed(1)}x</td>
          <td>${statusBadge}</td>
          <td style="color: #FAFAFA; font-weight: 700;">₹${row.target_2r.toFixed(2)}</td>
          <td>
            <button class="btn-inspect" onclick="window.selectSymbol('${row.full_symbol}')">
              <i class="fa-solid fa-chart-simple"></i> INSPECT
            </button>
          </td>
        </tr>
      `;
    });

    elements.screenerTableBody.innerHTML = html;

    // Attach Row Click
    elements.screenerTableBody.querySelectorAll('tr').forEach(tr => {
      tr.addEventListener('click', (e) => {
        if (e.target.closest('.btn-inspect')) return;
        const sym = tr.dataset.symbol;
        if (sym) {
          loadTickerChart(sym);
        }
      });
    });
  }

  // Global window helper for button onclick
  window.selectSymbol = function(sym) {
    loadTickerChart(sym);
  };

  /* ==========================================================================
     CHART & TICKER INSPECTOR
     ========================================================================== */
  async function loadTickerChart(symbol, forceRefresh = false) {
    if (!symbol) return;
    state.activeSymbol = symbol;

    if (elements.stockSelectorDropdown) {
      elements.stockSelectorDropdown.value = symbol;
    }

    // Highlight active row in table
    document.querySelectorAll('#screenerTableBody tr').forEach(tr => {
      tr.classList.toggle('active-row', tr.dataset.symbol === symbol);
    });

    elements.activeSymbolBadge.textContent = symbol.replace('.NS', '');

    try {
      let url = `/api/ticker/${encodeURIComponent(symbol)}?sw_len=${state.swLen}&atr_mult=${state.atrMult}&buy_pct_thresh=${state.buyConvictionPct / 100.0}`;
      const resp = await fetch(url);
      
      if (elements.refreshIcon) {
        elements.refreshIcon.classList.remove('fa-spin');
      }

      if (!resp.ok) {
        showToast(`Could not load chart data for ${symbol}`, 'warning');
        return;
      }

      const payload = await resp.json();
      state.chartData = payload;

      updateInspectorHUD(payload);
      renderPlotlyChart(payload);
    } catch (err) {
      console.error('[loadTickerChart] Error:', err);
      if (elements.refreshIcon) {
        elements.refreshIcon.classList.remove('fa-spin');
      }
    }
  }

  function updateInspectorHUD(data) {
    elements.activePrice.textContent = `₹${data.current_price.toFixed(2)}`;
    
    const isPos = data.change_abs >= 0;
    elements.activeChange.className = `active-change ${isPos ? 'text-emerald' : 'text-rose'}`;
    elements.activeChange.textContent = `${isPos ? '+' : ''}${data.change_pct.toFixed(2)}% (₹${data.change_abs.toFixed(2)})`;

    const stats = data.latest_stats;
    if (stats) {
      elements.hudBoxRange.textContent = `₹${stats.bottom.toFixed(2)} - ₹${stats.top.toFixed(2)}`;
      elements.hudBoxHeight.textContent = `HEIGHT: ₹${stats.box_height.toFixed(2)} (${stats.box_height_pct.toFixed(1)}%)`;
      
      elements.hudRetestStatus.innerHTML = stats.is_retesting 
        ? `<span class="text-accent" style="font-weight: 800;">RETESTING DEMAND BOX</span>`
        : `<span style="color: var(--text-secondary);">ABOVE ZONE</span>`;
      
      elements.hudFormationTime.textContent = `FORMED: ${stats.pivot_time_str || stats.pivot_time}`;
      elements.hudConviction.textContent = `${stats.buy_pct.toFixed(1)}%`;
      elements.hudRvol.textContent = `RVOL: ${stats.rvol.toFixed(2)}X`;
      elements.hudDisplacement.textContent = `₹${stats.displacement.toFixed(2)}`;
      elements.hudDispAtr.textContent = `${stats.disp_atr_ratio.toFixed(1)}X 14-ATR`;
      elements.hudTarget2r.textContent = `2R: ₹${stats.target_2r.toFixed(2)}`;
      elements.hudTarget3r.textContent = `3R: ₹${stats.target_3r.toFixed(2)}`;
    } else {
      elements.hudBoxRange.textContent = 'NO ACTIVE ZONE';
      elements.hudBoxHeight.textContent = '--';
      elements.hudRetestStatus.textContent = '--';
      elements.hudFormationTime.textContent = '--';
      elements.hudConviction.textContent = '--%';
      elements.hudRvol.textContent = '--';
      elements.hudDisplacement.textContent = '--';
      elements.hudDispAtr.textContent = '--';
      elements.hudTarget2r.textContent = '--';
      elements.hudTarget3r.textContent = '--';
    }
  }

  function renderPlotlyChart(data) {
    if (!window.Plotly || !elements.plotlyChartContainer) return;

    const candles = data.candles;
    if (!candles || candles.length === 0) {
      elements.plotlyChartContainer.innerHTML = `
        <div class="chart-placeholder">
          <p>NO CANDLESTICK DATA AVAILABLE FOR THIS TICKER.</p>
        </div>
      `;
      return;
    }

    const times = candles.map(c => c.time_str);
    const opens = candles.map(c => c.open);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const closes = candles.map(c => c.close);
    const volumes = candles.map(c => c.volume);
    const volSmas = candles.map(c => c.vol_sma);

    // Candle colors for volume bars (Kinetic Acid Yellow / Rose)
    const volColors = closes.map((c, i) => c >= opens[i] ? 'rgba(223, 225, 4, 0.75)' : 'rgba(239, 68, 68, 0.75)');

    // 1. Candlestick Trace (Subplot 1)
    const candlestickTrace = {
      type: 'candlestick',
      x: times,
      open: opens,
      high: highs,
      low: lows,
      close: closes,
      name: '15m Price',
      increasing: { line: { color: '#DFE104', width: 1.5 }, fillcolor: '#DFE104' },
      decreasing: { line: { color: '#EF4444', width: 1.5 }, fillcolor: '#EF4444' },
      xaxis: 'x',
      yaxis: 'y'
    };

    // 2. Volume Histogram Trace (Subplot 2)
    const volumeTrace = {
      type: 'bar',
      x: times,
      y: volumes,
      name: 'Volume',
      marker: { color: volColors },
      xaxis: 'x',
      yaxis: 'y2',
      showlegend: false
    };

    // 3. Volume 10-SMA Trace (Subplot 2)
    const volSmaTrace = {
      type: 'scatter',
      mode: 'lines',
      x: times,
      y: volSmas,
      name: '10-SMA Volume',
      line: { color: '#06B6D4', width: 1.5 },
      xaxis: 'x',
      yaxis: 'y2'
    };

    // Construct Shapes (Demand Boxes, Target Lines, Invalidation Lines)
    const shapes = [];
    const annotations = [];
    const latestTime = times[times.length - 1];

    if (data.zones && data.zones.length > 0) {
      data.zones.forEach((z, idx) => {
        const isLatest = (idx === data.zones.length - 1);
        const pivotTime = z.pivot_time_str || z.pivot_time;

        // Rectangle Demand Box Shape (Acid Yellow Brutalist High-Contrast Box)
        shapes.push({
          type: 'rect',
          xref: 'x',
          yref: 'y',
          x0: pivotTime,
          x1: latestTime,
          y0: z.bottom,
          y1: z.top,
          fillcolor: isLatest ? 'rgba(223, 225, 4, 0.22)' : 'rgba(223, 225, 4, 0.08)',
          line: {
            color: isLatest ? '#DFE104' : '#71717A',
            width: isLatest ? 2 : 1,
            dash: isLatest ? 'solid' : 'dot'
          }
        });

        // Annotation badge for latest active zone
        if (isLatest) {
          annotations.push({
            x: pivotTime,
            y: z.top,
            xref: 'x',
            yref: 'y',
            text: `DEMAND ZONE (${z.buy_pct.toFixed(0)}% BUY VOL)`,
            showarrow: true,
            arrowhead: 2,
            arrowsize: 1,
            arrowcolor: '#DFE104',
            ax: 0,
            ay: -24,
            bgcolor: '#DFE104',
            bordercolor: '#DFE104',
            borderwidth: 2,
            borderpad: 4,
            font: { color: '#000000', size: 10, family: 'Space Grotesk', weight: 800 }
          });

          // Target 2R Line
          if (z.target_2r) {
            shapes.push({
              type: 'line',
              xref: 'x',
              yref: 'y',
              x0: pivotTime,
              x1: latestTime,
              y0: z.target_2r,
              y1: z.target_2r,
              line: { color: '#FAFAFA', width: 1.5, dash: 'dash' }
            });

            annotations.push({
              x: latestTime,
              y: z.target_2r,
              xref: 'x',
              yref: 'y',
              text: `🎯 2R: ₹${z.target_2r.toFixed(2)}`,
              showarrow: false,
              xanchor: 'left',
              font: { color: '#FAFAFA', size: 10, family: 'JetBrains Mono', weight: 700 }
            });
          }

          // Invalidation Stop-Loss Line
          shapes.push({
            type: 'line',
            xref: 'x',
            yref: 'y',
            x0: pivotTime,
            x1: latestTime,
            y0: z.bottom,
            y1: z.bottom,
            line: { color: '#EF4444', width: 1.5, dash: 'dot' }
          });
        }
      });
    }

    // Layout configuration for Kinetic Typography Brutalist Chart
    const layout = {
      grid: { rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
      paper_bgcolor: '#09090B',
      plot_bgcolor: '#09090B',
      margin: { l: 20, r: 65, t: 20, b: 20 },
      showlegend: true,
      legend: {
        orientation: 'h',
        x: 1,
        y: 1.05,
        xanchor: 'right',
        font: { color: '#FAFAFA', size: 10, family: 'Space Grotesk' },
        bgcolor: 'rgba(0,0,0,0)'
      },
      hovermode: 'x unified',
      xaxis: {
        domain: [0, 1],
        rangeslider: { visible: false },
        gridcolor: '#27272A',
        showgrid: true,
        zeroline: false,
        tickfont: { color: '#71717A', size: 9, family: 'JetBrains Mono' },
        showticklabels: false
      },
      yaxis: {
        domain: [0.28, 1],
        side: 'right',
        gridcolor: '#27272A',
        showgrid: true,
        zeroline: false,
        tickfont: { color: '#FAFAFA', size: 10, family: 'JetBrains Mono' },
        tickprefix: '₹'
      },
      xaxis2: {
        domain: [0, 1],
        gridcolor: '#27272A',
        showgrid: true,
        zeroline: false,
        tickfont: { color: '#71717A', size: 9, family: 'JetBrains Mono' },
        matches: 'x'
      },
      yaxis2: {
        domain: [0, 0.22],
        side: 'right',
        gridcolor: '#27272A',
        showgrid: true,
        zeroline: false,
        tickfont: { color: '#71717A', size: 9, family: 'JetBrains Mono' }
      },
      shapes: shapes,
      annotations: annotations
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d']
    };

    Plotly.newPlot(elements.plotlyChartContainer, [candlestickTrace, volumeTrace, volSmaTrace], layout, config);
  }

  /* ==========================================================================
     TOAST NOTIFICATIONS (BRUTALIST TOASTS)
     ========================================================================== */
  function showToast(message, type = 'info') {
    if (!elements.toastContainer) return;

    const iconMap = {
      success: 'fa-circle-check',
      info: 'fa-circle-info',
      warning: 'fa-triangle-exclamation',
      error: 'fa-circle-xmark'
    };

    const icon = iconMap[type] || 'fa-circle-info';
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <i class="fa-solid ${icon}"></i>
      <span>${message.toUpperCase()}</span>
    `;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // Self Initialization on DOM load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
