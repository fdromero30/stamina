import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  LineChart,
  Loader2,
  Pause,
  Play,
  RefreshCw,
} from "lucide-react";
import { createChart, CandlestickSeries, LineSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { tradingCoreUrl } from "../data/dashboard";
import {
  useGetBotStatusQuery,
  useGetBotCyclesQuery,
  useStartBotMutation,
  useStopBotMutation,
  useTriggerCycleMutation,
  useGetChartDataQuery,
  type ChartData,
} from "../store/botApi";
import { CycleLog, OpenPositionsList } from "../components/CycleLog";
import type { Session } from "../types";

type StrategyChartPageProps = {
  session: Session;
};

type ChartSeriesRefs = {
  candleSeries: ISeriesApi<"Candlestick"> | null;
  ma9Series: ISeriesApi<"Line"> | null;
  ma200Series: ISeriesApi<"Line"> | null;
  chart: IChartApi | null;
};

function parseTime(time: string | Date | undefined | null): UTCTimestamp {
  // lightweight-charts expects Unix seconds (UTC)
  if (!time) {
    return Math.floor(Date.now() / 1000) as UTCTimestamp;
  }

  // If it's already a Date object or number, normalize it
  let timeStr: string;
  if (time instanceof Date) {
    timeStr = time.toISOString();
  } else if (typeof time === "number") {
    return Math.floor(time / 1000) as UTCTimestamp;
  } else {
    timeStr = String(time);
  }

  if (timeStr.startsWith("idx-")) {
    // Fallback for candles without timestamps: use a synthetic time
    return Math.floor(Date.now() / 1000) as UTCTimestamp;
  }

  // lightweight-charts requires timestamps in seconds (UTC).
  // eToro mock returns ISO strings with nanoseconds (up to 9 decimals),
  // which Date.parse() may not handle reliably, so we normalize to
  // milliseconds by keeping only the first 3 decimal digits.
  const normalized = timeStr.replace(/\.(\d{3})\d+/, ".$1");
  const parsed = Date.parse(normalized);
  if (!isNaN(parsed)) {
    return Math.floor(parsed / 1000) as UTCTimestamp;
  }

  return Math.floor(Date.now() / 1000) as UTCTimestamp;
}

function normalizeCandles(candles: ChartData["candles"]) {
  // lightweight-charts requires strictly increasing timestamps and
  // non-null OHLC values. Filter out invalid candles and duplicates.
  const seen = new Set<UTCTimestamp>();
  const result: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[] = [];
  for (const c of candles) {
    const t = parseTime(c.time);
    if (seen.has(t)) continue;
    if (c.open == null || c.high == null || c.low == null || c.close == null) continue;
    seen.add(t);
    result.push({
      time: t,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    });
  }
  // Sort by timestamp ascending (lightweight-charts requires increasing order)
  result.sort((a, b) => a.time - b.time);
  return result;
}

function normalizeLine(series: ChartData["ma9"]) {
  const seen = new Set<UTCTimestamp>();
  const result: { time: UTCTimestamp; value: number }[] = [];
  for (const p of series) {
    const t = parseTime(p.time);
    if (seen.has(t)) continue;
    if (p.value == null) continue;
    seen.add(t);
    result.push({ time: t, value: p.value });
  }
  // Sort by timestamp ascending (lightweight-charts requires increasing order)
  result.sort((a, b) => a.time - b.time);
  return result;
}

function updateChart(
  refs: ChartSeriesRefs,
  data: ChartData,
  prevDataRef: React.MutableRefObject<ChartData | null>
) {
  const { chart, candleSeries, ma9Series, ma200Series } = refs;
  if (!chart || !candleSeries || !ma9Series || !ma200Series) {
    console.warn("[Chart] updateChart skipped: series not ready");
    return;
  }

  const candles = normalizeCandles(data.candles);
  const ma9 = normalizeLine(data.ma9);
  const ma200 = normalizeLine(data.ma200);

  console.log("[Chart] updateChart:", {
    candles: candles.length,
    ma9: ma9.length,
    ma200: ma200.length,
    firstCandleTime: candles[0]?.time,
    lastCandleTime: candles[candles.length - 1]?.time,
  });

  try {
    // Only set data once on initial render, update incrementally afterwards
    if (!prevDataRef.current) {
      candleSeries.setData(candles);
      ma9Series.setData(ma9);
      ma200Series.setData(ma200);
      chart.timeScale().fitContent();
      console.log("[Chart] initial setData done");
    } else {
      // To avoid lightweight-charts "Cannot update oldest data" errors,
      // do a full setData() on every poll. This is safe because the
      // dataset is small (~300 candles) and lightweight-charts handles
      // setData() efficiently.
      candleSeries.setData(candles);
      ma9Series.setData(ma9);
      ma200Series.setData(ma200);
      console.log("[Chart] poll setData done");
    }
  } catch (error) {
    console.error("Failed to update chart:", error);
  }

  prevDataRef.current = data;
}

export function StrategyChartPage({ session }: StrategyChartPageProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartWrapperRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ChartSeriesRefs>({
    candleSeries: null,
    ma9Series: null,
    ma200Series: null,
    chart: null,
  });
  const prevDataRef = useRef<ChartData | null>(null);

  // ── View persistence (localStorage) ──────────────────────────────
  const VIEW_STORAGE_KEY = "stamina_chart_view";
  const loadView = (): { interval: string; symbol: string; chartHeight: number; chartWidth: number | null } => {
    try {
      const raw = localStorage.getItem(VIEW_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") {
          return {
            interval: parsed.interval ?? "5m",
            symbol: parsed.symbol ?? "EUR/USD",
            chartHeight: parsed.chartHeight ?? 480,
            chartWidth: parsed.chartWidth ?? null,
          };
        }
      }
    } catch {
      // ignore
    }
    return { interval: "5m", symbol: "EUR/USD", chartHeight: 480, chartWidth: null };
  };
  const initialView = loadView();

  const [interval, setInterval] = useState(initialView.interval);
  // Selected symbol for the chart. Defaults to EUR/USD but can be changed
  // independently of the symbol the trading engine is running on.
  const [symbol, setSymbol] = useState(initialView.symbol);
  // Track whether the user has manually chosen a symbol. Until they do, the
  // chart follows the bot's active strategy symbol.
  const userTouchedSymbolRef = useRef(false);
  const [symbolInput, setSymbolInput] = useState(initialView.symbol);
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);
  // Resizable chart height (px). Default matches the previous fixed height.
  const [chartHeight, setChartHeight] = useState(initialView.chartHeight);
  // Resizable chart width (px). null = full width (100%).
  const [chartWidth, setChartWidth] = useState<number | null>(initialView.chartWidth);
  const chartWidthRef = useRef<number | null>(initialView.chartWidth);

  // Persist view settings whenever they change (F5 keeps the same view)
  useEffect(() => {
    try {
      localStorage.setItem(
        VIEW_STORAGE_KEY,
        JSON.stringify({ interval, symbol, chartHeight, chartWidth })
      );
    } catch {
      // ignore
    }
  }, [interval, symbol, chartHeight, chartWidth]);

  // Preset symbols available in the combobox dropdown.
  const presetSymbols = ["EUR/USD", "BTC", "ETH", "GBP/USD", "XAU/USD", "AAPL", "TSLA"];

  // Keep the text input in sync with the selected symbol.
  useEffect(() => {
    setSymbolInput(symbol);
  }, [symbol]);

  const handleSymbolSelect = (value: string) => {
    userTouchedSymbolRef.current = true;
    setSymbol(value);
    setShowSymbolDropdown(false);
  };

  const handleSymbolInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSymbolInput(e.target.value);
  };

  const handleSymbolKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const trimmed = symbolInput.trim();
      if (trimmed) {
        userTouchedSymbolRef.current = true;
        setSymbol(trimmed.toUpperCase());
        setShowSymbolDropdown(false);
      }
    } else if (e.key === "Escape") {
      setShowSymbolDropdown(false);
    }
  };

  // ── RTK Query hooks ─────────────────────────────────────────────
  const {
    data: chartData,
    isLoading: chartLoading,
    isError: chartError,
    error: chartErrorObj,
    refetch: refetchChart,
  } = useGetChartDataQuery(
    { userId: session.id, symbol, interval, count: 300 },
    { pollingInterval: 5000 }
  );

  // Surface the backend error message (e.g. "No eToro API key configured
  // for user …") so the user knows the actual cause instead of a generic
  // "Is the Trading Core running?" message.
  const chartErrorMessage = (() => {
    if (!chartErrorObj) return null;
    const anyErr = chartErrorObj as any;
    const detail =
      anyErr?.data?.detail ??
      anyErr?.data?.message ??
      anyErr?.error ??
      String(anyErr?.status ?? "unknown error");
    return typeof detail === "string" ? detail : null;
  })();

  const { data: status } = useGetBotStatusQuery(undefined, { pollingInterval: 5000 });
  const { data: cyclesData } = useGetBotCyclesQuery(undefined, { pollingInterval: 5000 });

  // Active strategy from the bot (e.g. EUR/USD MA200+MA9 default). Until the
  // user picks a symbol manually, follow the strategy the bot is executing.
  const activeStrategy = status?.strategy;

  useEffect(() => {
    if (!userTouchedSymbolRef.current && activeStrategy?.symbol) {
      setSymbol(activeStrategy.symbol);
    }
  }, [activeStrategy?.symbol]);

  const [startBot, startResult] = useStartBotMutation();
  const [stopBot, stopResult] = useStopBotMutation();
  const [triggerCycle, cycleResult] = useTriggerCycleMutation();

  // Bot running state: use the live status endpoint, but fall back to the
  // chart's engine state while the status poll is still loading (this avoids
  // a frozen "—" countdown right after returning to the page).
  const engineRunningFromChart = chartData?.engine?.running ?? false;
  const isRunning = (status?.running ?? false) || engineRunningFromChart;

  // ── Countdown to next cycle ──────────────────────────────────────
  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    // NOTE: `interval` state shadows the global setInterval, so use
    // window.setInterval explicitly for the countdown ticker.
    const ticker = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(ticker);
  }, []);

  // Use backend next_run when available; otherwise compute the next 5-minute
  // aligned boundary locally (+2s margin) so the countdown always ticks.
  const computedNextRun = (() => {
    const now = new Date(nowTick);
    const intervalMs = (status?.interval_seconds ?? 300) * 1000;
    const boundary = (Math.floor(now.getTime() / intervalMs) + 1) * intervalMs;
    return boundary + 2000; // +2s margin for closed candle
  })();

  const nextRunTime = status?.next_run
    ? new Date(status.next_run).getTime()
    : isRunning
      ? computedNextRun
      : null;
  const secondsRemaining = nextRunTime != null
    ? Math.max(0, Math.floor((nextRunTime - nowTick) / 1000))
    : null;

  // ── Create chart once on mount ──────────────────────────────────
  useEffect(() => {
    console.log("[Chart] mount, container:", chartContainerRef.current);
    if (!chartContainerRef.current) return;

    const containerWidth = chartContainerRef.current.clientWidth || 800;
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "#ffffff" },
        textColor: "#334443",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "#eef2f0" },
        horzLines: { color: "#eef2f0" },
      },
      rightPriceScale: {
        borderColor: "#dde5e2",
      },
      timeScale: {
        borderColor: "#dde5e2",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 0, // normal
      },
      width: containerWidth,
      height: 480,
    });

    // Show prices with the same precision eToro provides (5 decimals for FX,
    // keeping pips visible). This also affects the right price scale.
    const priceFormat = {
      type: "price" as const,
      precision: 5,
      minMove: 0.00001,
    };

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#1f7a57",
      downColor: "#a14535",
      borderUpColor: "#1f7a57",
      borderDownColor: "#a14535",
      wickUpColor: "#1f7a57",
      wickDownColor: "#a14535",
      priceFormat,
    });

    const ma9Series = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: "MA9",
      priceFormat,
    });

    const ma200Series = chart.addSeries(LineSeries, {
      color: "#d97706",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: "MA200",
      priceFormat,
    });

    chartRef.current.candleSeries = candleSeries;
    chartRef.current.ma9Series = ma9Series;
    chartRef.current.ma200Series = ma200Series;
    chartRef.current.chart = chart;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current.chart) {
        chartRef.current.chart.applyOptions({
          width: chartWidthRef.current ?? chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    // Ensure the chart renders after data is set
    setTimeout(() => {
      if (chartRef.current.chart && chartContainerRef.current) {
        const w = chartWidthRef.current ?? (chartContainerRef.current.clientWidth || 800);
        chartRef.current.chart.resize(w, chartHeight);
      }
    }, 100);

    console.log("[Chart] chart created, containerWidth:", containerWidth);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = { candleSeries: null, ma9Series: null, ma200Series: null, chart: null };
      prevDataRef.current = null;
    };
  }, []);

  // ── Resize chart when the user changes height or width ────────────
  useEffect(() => {
    const { chart } = chartRef.current;
    const width = chartWidthRef.current ?? chartContainerRef.current?.clientWidth;
    if (chart) {
      chart.applyOptions({ height: chartHeight });
      if (width) {
        chart.applyOptions({ width });
      }
    }
    if (chartContainerRef.current) {
      chartContainerRef.current.style.height = `${chartHeight}px`;
    }
    if (chartWrapperRef.current) {
      chartWrapperRef.current.style.width = chartWidth ? `${chartWidth}px` : "100%";
      chartWrapperRef.current.style.maxWidth = "100%";
    }
  }, [chartHeight, chartWidth]);

  // ── Feed data to chart when it arrives ──────────────────────────
  useEffect(() => {
    if (chartData) {
      console.log("[Chart] data received:", {
        symbol: chartData.symbol,
        candles: chartData.candles.length,
        ma9: chartData.ma9.length,
        ma200: chartData.ma200.length,
        engine: chartData.engine,
      });
      updateChart(chartRef.current, chartData, prevDataRef);

      // Force a resize after setting data to ensure the chart renders
      if (chartContainerRef.current && chartRef.current.chart) {
        const w = chartWidthRef.current ?? (chartContainerRef.current.clientWidth || 800);
        chartRef.current.chart.resize(w, chartHeight);
      }
    }
  }, [chartData]);

  // ── Auto-refetch chart on key events ────────────────────────────
  useEffect(() => {
    refetchChart();
  }, [symbol, isRunning]);

  // ── Reset chart data when interval changes ──────────────────────
  useEffect(() => {
    prevDataRef.current = null;
    // Clear existing series data so the chart re-renders with new interval data
    const { candleSeries, ma9Series, ma200Series } = chartRef.current;
    if (candleSeries) candleSeries.setData([]);
    if (ma9Series) ma9Series.setData([]);
    if (ma200Series) ma200Series.setData([]);
  }, [interval]);

  // ── Reset chart data when symbol changes ────────────────────────
  useEffect(() => {
    prevDataRef.current = null;
    const { candleSeries, ma9Series, ma200Series } = chartRef.current;
    if (candleSeries) candleSeries.setData([]);
    if (ma9Series) ma9Series.setData([]);
    if (ma200Series) ma200Series.setData([]);
  }, [symbol]);

  const handleStart = async () => {
    try {
      await startBot().unwrap();
    } catch (err: any) {
      console.error("Failed to start bot:", err);
    }
  };

  const handleStop = async () => {
    try {
      await stopBot().unwrap();
    } catch (err: any) {
      console.error("Failed to stop bot:", err);
    }
  };

  const handleCycle = async () => {
    try {
      await triggerCycle().unwrap();
    } catch (err: any) {
      console.error("Failed to run manual cycle:", err);
    }
  };

  // Drag-to-resize: start capturing pointer movement on the bottom handle.
  const handleResizeDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = chartHeight;
    const onMouseMove = (ev: MouseEvent) => {
      const deltaY = ev.clientY - startY;
      const nextHeight = Math.min(900, Math.max(220, startHeight + deltaY));
      setChartHeight(nextHeight);
    };
    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    document.body.style.cursor = "ns-resize";
    document.body.style.userSelect = "none";
  };

  // Drag-to-resize width: capture pointer movement on the right handle.
  const handleWidthDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    const startX = e.clientX;
    // On first drag, the maximum width is the full panel width (available space).
    const maxWidth = chartWrapperRef.current?.parentElement?.clientWidth ?? 800;
    const startWidth = chartWidthRef.current ?? maxWidth;
    const onMouseMove = (ev: MouseEvent) => {
      const deltaX = ev.clientX - startX;
      const nextWidth = Math.min(maxWidth, Math.max(320, startWidth + deltaX));
      chartWidthRef.current = nextWidth;
      setChartWidth(nextWidth);
    };
    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  };

  const lastBid = chartData?.last_price?.bid ?? null;
  const lastAsk = chartData?.last_price?.ask ?? null;
  const mid = lastBid != null && lastAsk != null ? (lastBid + lastAsk) / 2 : null;
  // Spread = difference between ask and bid, shown in % (what eToro charges).
  const spreadPct = lastBid != null && lastAsk != null && lastBid > 0
    ? ((lastAsk - lastBid) / lastBid) * 100
    : null;
  const lastTimestamp = chartData?.timestamp ? new Date(chartData.timestamp).toLocaleTimeString() : "—";

  // ── Engine state (deterministic state for trade execution) ──────
  const engine = chartData?.engine;
  const engineRunning = engine?.running ?? false;
  const engineStartedAt = engine?.started_at
    ? new Date(engine.started_at).toLocaleTimeString()
    : "—";
  const openPositionsCount = Object.values(engine?.open_positions ?? {}).reduce(
    (sum, positions) => sum + (positions?.length ?? 0),
    0
  );
  const lastSignal = engine?.last_evaluation?.signal;
  const lastSignalAction = lastSignal?.action ?? "—";
  const lastSignalConfidence = lastSignal?.confidence;

  return (
    <section className="panel chart-panel">
      <div className="panel-header">
        <LineChart size={20} color="#1f7a57" />
        <h2>Strategy Chart — {symbol}</h2>
        {isRunning ? (
          <span className="bot-status-badge bot-status-running">
            <CheckCircle2 size={12} /> Running
          </span>
        ) : (
          <span className="bot-status-badge bot-status-stopped">
            <Pause size={12} /> Stopped
          </span>
        )}
      </div>

      <p className="etoro-test-subtitle">
        Connected as <strong>{session.name}</strong> &mdash; Trading Core: <code>{tradingCoreUrl}</code>
      </p>

      {/* ── Symbol selector (combobox: presets + free text) ── */}
      <div className="chart-symbol-selector">
        <label>Asset:</label>
        <div className="symbol-combobox">
          <input
            type="text"
            value={symbolInput}
            onChange={handleSymbolInput}
            onKeyDown={handleSymbolKeyDown}
            onFocus={() => setShowSymbolDropdown(true)}
            onBlur={() => setTimeout(() => setShowSymbolDropdown(false), 150)}
            className="symbol-input"
            placeholder="e.g. BTC, EUR/USD"
          />
          <button
            className="ghost-button small"
            onClick={() => setShowSymbolDropdown((v) => !v)}
            aria-label="Toggle asset list"
          >
            ▼
          </button>
          {showSymbolDropdown && (
            <ul className="symbol-dropdown">
              {presetSymbols.map((s) => (
                <li key={s}>
                  <button
                    className="symbol-option"
                    onClick={() => handleSymbolSelect(s)}
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ── Bot Controls ── */}
      <div className="chart-controls-row">
        <div className="chart-bot-controls">
          {!isRunning ? (
            <button className="primary-button small" onClick={handleStart} disabled={startResult.isLoading}>
              {startResult.isLoading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
              <span>Start Bot</span>
            </button>
          ) : (
            <button className="secondary-button small" onClick={handleStop} disabled={stopResult.isLoading}>
              {stopResult.isLoading ? <Loader2 size={14} className="spin" /> : <Pause size={14} />}
              <span>Stop Bot</span>
            </button>
          )}
          <button className="secondary-button small" onClick={handleCycle} disabled={cycleResult.isLoading}>
            {cycleResult.isLoading ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
            <span>Run Cycle</span>
          </button>
          <button className="ghost-button small" onClick={refetchChart} disabled={chartLoading}>
            <RefreshCw size={14} />
            <span>Refresh Chart</span>
          </button>
        </div>

        <div className="chart-interval-selector">
          <label>Interval:</label>
          <select value={interval} onChange={(e) => setInterval(e.target.value)}>
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
          </select>
        </div>

      </div>

      {/* ── Live Price Ticker ── */}
      <div className="chart-live-ticker">
        <div className="ticker-item">
          <span className="ticker-label">Bid</span>
          <strong className={lastBid != null ? "ticker-value" : "ticker-value ticker-muted"}>
            {lastBid != null ? lastBid.toFixed(5) : "—"}
          </strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Ask</span>
          <strong className={lastAsk != null ? "ticker-value" : "ticker-value ticker-muted"}>
            {lastAsk != null ? lastAsk.toFixed(5) : "—"}
          </strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Mid</span>
          <strong className={mid != null ? "ticker-value" : "ticker-value ticker-muted"}>
            {mid != null ? mid.toFixed(5) : "—"}
          </strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Spread</span>
          <strong className={spreadPct != null ? "ticker-value ticker-spread" : "ticker-value ticker-muted"}>
            {spreadPct != null ? `${spreadPct.toFixed(3)}%` : "—"}
          </strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Updated</span>
          <strong className="ticker-value ticker-time">{lastTimestamp}</strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Cycles</span>
          <strong className="ticker-value">{status?.cycles_completed ?? 0}</strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Interval</span>
          <strong className="ticker-value">{status ? `${Math.round(status.interval_seconds / 60)} min` : "—"}</strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Engine</span>
          <strong className={engineRunning ? "ticker-value ticker-running" : "ticker-value ticker-muted"}>
            {engineRunning ? "Running" : "Stopped"}
          </strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Started</span>
          <strong className="ticker-value">{engineStartedAt}</strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Positions</span>
          <strong className="ticker-value">{openPositionsCount}</strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Last Signal</span>
          <strong className="ticker-value">
            {lastSignalAction}
            {lastSignalConfidence != null ? ` (${(lastSignalConfidence * 100).toFixed(0)}%)` : ""}
          </strong>
        </div>
        <div className="ticker-item">
          <span className="ticker-label">Next Cycle</span>
          <strong className={secondsRemaining != null ? "ticker-value ticker-countdown" : "ticker-value ticker-muted"}>
            {secondsRemaining != null
              ? `${Math.floor(secondsRemaining / 60)}:${String(secondsRemaining % 60).padStart(2, "0")}`
              : "—"}
          </strong>
        </div>
      </div>

      {/* ── Chart + Cycle Log (50/50) ── */}
      <div className="chart-layout-split">
        <div className="chart-column">
          <div className="chart-wrapper" ref={chartWrapperRef}>
            {chartLoading && !chartData && (
              <div className="chart-loading">
                <Loader2 size={24} className="spin" />
                <span>Loading chart data…</span>
              </div>
            )}
            {chartError && !chartData && (
              <div className="chart-error">
                <AlertCircle size={24} />
                <span>
                  {chartErrorMessage
                    ? `Error loading chart data: ${chartErrorMessage}`
                    : "Error loading chart data. Is the Trading Core running?"}
                </span>
              </div>
            )}
            <div ref={chartContainerRef} className="chart-container" style={{ height: chartHeight }} />
            {/* Drag handle para redimensionar el ancho con el ratón */}
            <div
              className="chart-resize-handle chart-resize-handle-x"
              onMouseDown={handleWidthDragStart}
              title="Arrastra para redimensionar el ancho de la gráfica"
            >
              <span>⠿</span>
            </div>
            {/* Drag handle para redimensionar la altura con el ratón */}
            <div
              className="chart-resize-handle chart-resize-handle-y"
              onMouseDown={handleResizeDragStart}
              title="Arrastra para redimensionar la altura de la gráfica"
            >
              <span>⠿</span>
            </div>
          </div>

          {/* ── Legend ── */}
          <div className="chart-legend">
            <span className="legend-item">
              <span className="legend-line" style={{ background: "#2563eb" }} />
              MA9
            </span>
            <span className="legend-item">
              <span className="legend-line" style={{ background: "#d97706" }} />
              MA200
            </span>
            <span className="legend-item">
              <span className="legend-candle-up" />
              Bullish
            </span>
            <span className="legend-item">
              <span className="legend-candle-down" />
              Bearish
            </span>
          </div>
        </div>

        {/* Cycle log column (most recent first, with scroll) */}
        <div className="chart-column">
          <CycleLog />
        </div>
      </div>

      {/* ── Open Positions (full width, below the split) ── */}
      <div className="open-positions-section">
        <h3>Open Positions</h3>
        <div className="etoro-test-card">
          <OpenPositionsList positions={cyclesData?.open_positions ?? {}} />
        </div>
      </div>
    </section>
  );
}