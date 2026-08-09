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
  useStartBotMutation,
  useStopBotMutation,
  useTriggerCycleMutation,
  useGetChartDataQuery,
  type ChartData,
} from "../store/botApi";
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

function parseTime(time: string): UTCTimestamp {
  // lightweight-charts expects Unix seconds (UTC)
  if (time.startsWith("idx-")) {
    // Fallback for candles without timestamps: use a synthetic time
    return Math.floor(Date.now() / 1000) as UTCTimestamp;
  }
  const parsed = Date.parse(time);
  if (!isNaN(parsed)) {
    return Math.floor(parsed / 1000) as UTCTimestamp;
  }
  return Math.floor(Date.now() / 1000) as UTCTimestamp;
}

function updateChart(
  refs: ChartSeriesRefs,
  data: ChartData,
  prevDataRef: React.MutableRefObject<ChartData | null>
) {
  const { chart, candleSeries, ma9Series, ma200Series } = refs;
  if (!chart || !candleSeries || !ma9Series || !ma200Series) return;

  // Only set data once on initial render, update incrementally afterwards
  if (!prevDataRef.current) {
    candleSeries.setData(
      data.candles.map((c) => ({
        time: parseTime(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );
    ma9Series.setData(
      data.ma9.map((p) => ({ time: parseTime(p.time), value: p.value }))
    );
    ma200Series.setData(
      data.ma200.map((p) => ({ time: parseTime(p.time), value: p.value }))
    );
    chart.timeScale().fitContent();
  } else {
    // Incremental update: add new candles / update last candle
    const prevCandles = prevDataRef.current.candles;
    const newCandles = data.candles;

    // If the number of candles changed significantly, do a full reset
    if (Math.abs(newCandles.length - prevCandles.length) > 2) {
      candleSeries.setData(
        newCandles.map((c) => ({
          time: parseTime(c.time),
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
      );
      ma9Series.setData(
        data.ma9.map((p) => ({ time: parseTime(p.time), value: p.value }))
      );
      ma200Series.setData(
        data.ma200.map((p) => ({ time: parseTime(p.time), value: p.value }))
      );
    } else {
      // Find new candles that weren't in the previous data
      const prevTimes = new Set(prevCandles.map((c) => c.time));
      const newCandlesToAdd = newCandles.filter((c) => !prevTimes.has(c.time));

      // Add new candles
      for (const c of newCandlesToAdd) {
        candleSeries.update({
          time: parseTime(c.time),
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        });
      }

      // Update the last candle in place (for the currently forming candle)
      if (newCandles.length > 0) {
        const lastCandle = newCandles[newCandles.length - 1];
        candleSeries.update({
          time: parseTime(lastCandle.time),
          open: lastCandle.open,
          high: lastCandle.high,
          low: lastCandle.low,
          close: lastCandle.close,
        });
      }

      // Update last MA points
      if (data.ma9.length > 0) {
        const lastMa9 = data.ma9[data.ma9.length - 1];
        ma9Series.update({ time: parseTime(lastMa9.time), value: lastMa9.value });
      }
      if (data.ma200.length > 0) {
        const lastMa200 = data.ma200[data.ma200.length - 1];
        ma200Series.update({ time: parseTime(lastMa200.time), value: lastMa200.value });
      }
    }
  }

  prevDataRef.current = data;
}

export function StrategyChartPage({ session }: StrategyChartPageProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ChartSeriesRefs>({
    candleSeries: null,
    ma9Series: null,
    ma200Series: null,
    chart: null,
  });
  const prevDataRef = useRef<ChartData | null>(null);

  const [interval, setInterval] = useState("5m");

  // ── RTK Query hooks ─────────────────────────────────────────────
  const { data: chartData, isLoading: chartLoading, isError: chartError, refetch: refetchChart } =
    useGetChartDataQuery(
      { userId: session.id, interval, count: 300 },
      { pollingInterval: 5000 }
    );

  const { data: status } = useGetBotStatusQuery(undefined, { pollingInterval: 5000 });

  const [startBot, startResult] = useStartBotMutation();
  const [stopBot, stopResult] = useStopBotMutation();
  const [triggerCycle, cycleResult] = useTriggerCycleMutation();

  const isRunning = status?.running ?? false;

  // ── Create chart once on mount ──────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current) return;

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
      width: chartContainerRef.current.clientWidth,
      height: 480,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#1f7a57",
      downColor: "#a14535",
      borderUpColor: "#1f7a57",
      borderDownColor: "#a14535",
      wickUpColor: "#1f7a57",
      wickDownColor: "#a14535",
    });

    const ma9Series = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: "MA9",
    });

    const ma200Series = chart.addSeries(LineSeries, {
      color: "#d97706",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: "MA200",
    });

    chartRef.current.candleSeries = candleSeries;
    chartRef.current.ma9Series = ma9Series;
    chartRef.current.ma200Series = ma200Series;
    chartRef.current.chart = chart;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current.chart) {
        chartRef.current.chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = { candleSeries: null, ma9Series: null, ma200Series: null, chart: null };
      prevDataRef.current = null;
    };
  }, []);

  // ── Feed data to chart when it arrives ──────────────────────────
  useEffect(() => {
    if (chartData) {
      updateChart(chartRef.current, chartData, prevDataRef);
    }
  }, [chartData]);

  // ── Reset chart data when interval changes ──────────────────────
  useEffect(() => {
    prevDataRef.current = null;
    // Clear existing series data so the chart re-renders with new interval data
    const { candleSeries, ma9Series, ma200Series } = chartRef.current;
    if (candleSeries) candleSeries.setData([]);
    if (ma9Series) ma9Series.setData([]);
    if (ma200Series) ma200Series.setData([]);
  }, [interval]);

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

  const lastBid = chartData?.last_price?.bid ?? null;
  const lastAsk = chartData?.last_price?.ask ?? null;
  const mid = lastBid != null && lastAsk != null ? (lastBid + lastAsk) / 2 : null;
  const lastTimestamp = chartData?.timestamp ? new Date(chartData.timestamp).toLocaleTimeString() : "—";

  return (
    <section className="panel chart-panel">
      <div className="panel-header">
        <LineChart size={20} color="#1f7a57" />
        <h2>Strategy Chart — EUR/USD</h2>
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
      </div>

      {/* ── Chart ── */}
      <div className="chart-wrapper">
        {chartLoading && !chartData && (
          <div className="chart-loading">
            <Loader2 size={24} className="spin" />
            <span>Loading chart data…</span>
          </div>
        )}
        {chartError && !chartData && (
          <div className="chart-error">
            <AlertCircle size={24} />
            <span>Error loading chart data. Is the Trading Core running?</span>
          </div>
        )}
        <div ref={chartContainerRef} className="chart-container" />
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
    </section>
  );
}