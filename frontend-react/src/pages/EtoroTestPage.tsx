import { useState } from "react";
import { Activity, AlertCircle, CheckCircle2, ExternalLink, Loader2, Search, TrendingUp, XCircle } from "lucide-react";
import type { Session } from "../types";
import {
  useLazySearchInstrumentsQuery,
  useLazyGetInstrumentRatesQuery,
  useLazyGetCandlesQuery,
  useLazyGetPortfolioQuery,
  useLazyGetDemoPortfolioQuery,
  useLazyGetRealPnlQuery,
  useLazyGetDemoPnlQuery,
  useLazyGetTradeHistoryQuery,
  useDemoOpenByAmountMutation,
} from "../store/etoroApi";

type EtoroTestPageProps = {
  session: Session;
};

type ApiCallStatus = "idle" | "loading" | "success" | "error";

type CallResult = {
  label: string;
  status: ApiCallStatus;
  data?: any;
  error?: string;
  timestamp?: string;
};

export function EtoroTestPage({ session }: EtoroTestPageProps) {
  // Search
  const [query, setQuery] = useState("BTC");
  const [triggerSearch, searchResult] = useLazySearchInstrumentsQuery();

  // Rates
  const [instrumentIds, setInstrumentIds] = useState("100000");
  const [triggerRates, ratesResult] = useLazyGetInstrumentRatesQuery();

  // Candles
  const [candleInstrumentId, setCandleInstrumentId] = useState("100000");
  const [candleInterval, setCandleInterval] = useState("1h");
  const [triggerCandles, candlesResult] = useLazyGetCandlesQuery();

  // Portfolio
  const [triggerPortfolio, portfolioResult] = useLazyGetPortfolioQuery();
  const [triggerDemoPortfolio, demoPortfolioResult] = useLazyGetDemoPortfolioQuery();

  // P&L
  const [triggerRealPnl, realPnlResult] = useLazyGetRealPnlQuery();
  const [triggerDemoPnl, demoPnlResult] = useLazyGetDemoPnlQuery();

  // Trade history
  const [minDate, setMinDate] = useState("2024-01-01");
  const [triggerTradeHistory, tradeHistoryResult] = useLazyGetTradeHistoryQuery();

  // Demo open by amount
  const [demoInstrumentId, setDemoInstrumentId] = useState("100000");
  const [demoAmount, setDemoAmount] = useState("100");
  const [triggerDemoOpen, demoOpenResult] = useDemoOpenByAmountMutation();

  // Consolidated results
  const [results, setResults] = useState<CallResult[]>([]);

  const addResult = (label: string, status: ApiCallStatus, data?: any, error?: string) => {
    setResults((prev) => [
      { label, status, data, error, timestamp: new Date().toLocaleTimeString() },
      ...prev.slice(0, 19), // keep last 20
    ]);
  };

  const handleSearch = async () => {
    addResult(`SEARCH "${query}"`, "loading");
    try {
      const data = await triggerSearch({ userId: session.id, q: query }).unwrap();
      addResult(`SEARCH "${query}"`, "success", data);
    } catch (err: any) {
      addResult(`SEARCH "${query}"`, "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleRates = async () => {
    const ids = instrumentIds.split(",").map(Number).filter((n) => !isNaN(n));
    addResult(`RATES [${ids.join(",")}]`, "loading");
    try {
      const data = await triggerRates({ userId: session.id, instrumentIds: ids }).unwrap();
      addResult(`RATES [${ids.join(",")}]`, "success", data);
    } catch (err: any) {
      addResult(`RATES [${ids.join(",")}]`, "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleCandles = async () => {
    const id = Number(candleInstrumentId);
    addResult(`CANDLES ${id} (${candleInterval})`, "loading");
    try {
      const data = await triggerCandles({ userId: session.id, instrumentId: id, interval: candleInterval }).unwrap();
      addResult(`CANDLES ${id} (${candleInterval})`, "success", data);
    } catch (err: any) {
      addResult(`CANDLES ${id} (${candleInterval})`, "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handlePortfolio = async () => {
    addResult("PORTFOLIO (real)", "loading");
    try {
      const data = await triggerPortfolio({ userId: session.id }).unwrap();
      addResult("PORTFOLIO (real)", "success", data);
    } catch (err: any) {
      addResult("PORTFOLIO (real)", "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleDemoPortfolio = async () => {
    addResult("PORTFOLIO (demo)", "loading");
    try {
      const data = await triggerDemoPortfolio({ userId: session.id }).unwrap();
      addResult("PORTFOLIO (demo)", "success", data);
    } catch (err: any) {
      addResult("PORTFOLIO (demo)", "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleRealPnl = async () => {
    addResult("P&L (real)", "loading");
    try {
      const data = await triggerRealPnl({ userId: session.id }).unwrap();
      addResult("P&L (real)", "success", data);
    } catch (err: any) {
      addResult("P&L (real)", "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleDemoPnl = async () => {
    addResult("P&L (demo)", "loading");
    try {
      const data = await triggerDemoPnl({ userId: session.id }).unwrap();
      addResult("P&L (demo)", "success", data);
    } catch (err: any) {
      addResult("P&L (demo)", "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleTradeHistory = async () => {
    addResult(`TRADE HISTORY (since ${minDate})`, "loading");
    try {
      const data = await triggerTradeHistory({ userId: session.id, minDate }).unwrap();
      addResult(`TRADE HISTORY (since ${minDate})`, "success", data);
    } catch (err: any) {
      addResult(`TRADE HISTORY (since ${minDate})`, "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  const handleDemoOpen = async () => {
    const id = Number(demoInstrumentId);
    const amt = Number(demoAmount);
    addResult(`DEMO OPEN ${id} x$${amt}`, "loading");
    try {
      const data = await triggerDemoOpen({ userId: session.id, instrumentId: id, isBuy: true, amount: amt }).unwrap();
      addResult(`DEMO OPEN ${id} x$${amt}`, "success", data);
    } catch (err: any) {
      addResult(`DEMO OPEN ${id} x$${amt}`, "error", null, err?.data?.message ?? err?.message ?? "Unknown error");
    }
  };

  return (
    <section className="panel etoro-test-panel">
      <div className="panel-header">
        <Activity size={20} color="#1f7a57" />
        <h2>eToro API Test Console</h2>
      </div>

      <p className="etoro-test-subtitle">
        Connected as <strong>{session.name}</strong> ({session.email}) &mdash; User ID: <code>{session.id}</code>
      </p>

      <div className="etoro-test-grid">
        {/* ── Market Data ── */}
        <div className="etoro-test-section">
          <h3><Search size={16} /> Market Data</h3>

          <div className="etoro-test-card">
            <label>Search Instruments</label>
            <div className="etoro-test-row">
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. BTC" />
              <button className="primary-button small" onClick={handleSearch} disabled={searchResult.isLoading}>
                {searchResult.isLoading ? <Loader2 size={14} className="spin" /> : <Search size={14} />}
                <span>Search</span>
              </button>
            </div>
          </div>

          <div className="etoro-test-card">
            <label>Instrument Rates</label>
            <div className="etoro-test-row">
              <input value={instrumentIds} onChange={(e) => setInstrumentIds(e.target.value)} placeholder="e.g. 100000,100001" />
              <button className="primary-button small" onClick={handleRates} disabled={ratesResult.isLoading}>
                {ratesResult.isLoading ? <Loader2 size={14} className="spin" /> : <TrendingUp size={14} />}
                <span>Get Rates</span>
              </button>
            </div>
          </div>

          <div className="etoro-test-card">
            <label>Candles</label>
            <div className="etoro-test-row">
              <input value={candleInstrumentId} onChange={(e) => setCandleInstrumentId(e.target.value)} placeholder="Instrument ID" style={{ flex: 1 }} />
              <select value={candleInterval} onChange={(e) => setCandleInterval(e.target.value)} style={{ width: 80 }}>
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
                <option value="1d">1d</option>
              </select>
              <button className="primary-button small" onClick={handleCandles} disabled={candlesResult.isLoading}>
                {candlesResult.isLoading ? <Loader2 size={14} className="spin" /> : <TrendingUp size={14} />}
                <span>Candles</span>
              </button>
            </div>
          </div>
        </div>

        {/* ── Portfolio & P&L ── */}
        <div className="etoro-test-section">
          <h3><Activity size={16} /> Portfolio & P&L</h3>

          <div className="etoro-test-card">
            <div className="etoro-test-row" style={{ justifyContent: "flex-start", gap: 10 }}>
              <button className="primary-button small" onClick={handlePortfolio} disabled={portfolioResult.isLoading}>
                {portfolioResult.isLoading ? <Loader2 size={14} className="spin" /> : null}
                <span>Real Portfolio</span>
              </button>
              <button className="secondary-button small" onClick={handleDemoPortfolio} disabled={demoPortfolioResult.isLoading}>
                {demoPortfolioResult.isLoading ? <Loader2 size={14} className="spin" /> : null}
                <span>Demo Portfolio</span>
              </button>
            </div>
          </div>

          <div className="etoro-test-card">
            <div className="etoro-test-row" style={{ justifyContent: "flex-start", gap: 10 }}>
              <button className="primary-button small" onClick={handleRealPnl} disabled={realPnlResult.isLoading}>
                {realPnlResult.isLoading ? <Loader2 size={14} className="spin" /> : null}
                <span>Real P&L</span>
              </button>
              <button className="secondary-button small" onClick={handleDemoPnl} disabled={demoPnlResult.isLoading}>
                {demoPnlResult.isLoading ? <Loader2 size={14} className="spin" /> : null}
                <span>Demo P&L</span>
              </button>
            </div>
          </div>

          <div className="etoro-test-card">
            <label>Trade History</label>
            <div className="etoro-test-row">
              <input type="date" value={minDate} onChange={(e) => setMinDate(e.target.value)} />
              <button className="primary-button small" onClick={handleTradeHistory} disabled={tradeHistoryResult.isLoading}>
                {tradeHistoryResult.isLoading ? <Loader2 size={14} className="spin" /> : null}
                <span>History</span>
              </button>
            </div>
          </div>
        </div>

        {/* ── Trading Execution ── */}
        <div className="etoro-test-section">
          <h3><ExternalLink size={16} /> Trading (Demo)</h3>

          <div className="etoro-test-card">
            <label>Demo Open By Amount</label>
            <div className="etoro-test-row">
              <input value={demoInstrumentId} onChange={(e) => setDemoInstrumentId(e.target.value)} placeholder="Instrument ID" style={{ flex: 1 }} />
              <input type="number" value={demoAmount} onChange={(e) => setDemoAmount(e.target.value)} placeholder="Amount" style={{ width: 100 }} />
              <button className="primary-button small" onClick={handleDemoOpen} disabled={demoOpenResult.isLoading}>
                {demoOpenResult.isLoading ? <Loader2 size={14} className="spin" /> : null}
                <span>Open</span>
              </button>
            </div>
            <p className="field-hint">Creates a demo BUY market order. Make sure your eToro API key is configured.</p>
          </div>
        </div>
      </div>

      {/* ── Results Log ── */}
      <div className="etoro-test-log">
        <h3>API Response Log</h3>
        {results.length === 0 && (
          <p className="panel-muted">No calls yet. Click any button above to fire a request.</p>
        )}
        {results.map((r, i) => (
          <div key={i} className={`etoro-log-entry etoro-log-${r.status}`}>
            <div className="etoro-log-header">
              <span className="etoro-log-status">
                {r.status === "loading" && <Loader2 size={14} className="spin" />}
                {r.status === "success" && <CheckCircle2 size={14} color="#1f7a57" />}
                {r.status === "error" && <XCircle size={14} color="#a14535" />}
                {r.status === "idle" && <AlertCircle size={14} color="#8a9e98" />}
              </span>
              <strong>{r.label}</strong>
              <span className="etoro-log-time">{r.timestamp}</span>
            </div>
            {r.status === "success" && r.data && (
              <pre className="etoro-log-data">{JSON.stringify(r.data, null, 2).slice(0, 2000)}</pre>
            )}
            {r.status === "error" && r.error && (
              <pre className="etoro-log-error">{r.error}</pre>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}