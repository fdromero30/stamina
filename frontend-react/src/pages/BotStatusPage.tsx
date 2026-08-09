import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  Activity,
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Server,
  TrendingDown,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { tradingCoreUrl } from "../data/dashboard";
import {
  useGetBotStatusQuery,
  useStartBotMutation,
  useStopBotMutation,
  useTriggerCycleMutation,
  useGetBotCyclesQuery,
  useLazyGetHealthQuery,
  type CycleHistoryEntry,
  type OpenPosition,
} from "../store/botApi";
import { cacheBotStatus, cacheBotCycles, clearBotCache } from "../store/botStateSlice";
import type { RootState } from "../store/store";
import type { Session } from "../types";

type BotStatusPageProps = {
  session: Session;
};

type LogEntry = {
  id: number;
  label: string;
  status: "loading" | "success" | "error";
  data?: any;
  error?: string;
  timestamp: string;
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function SignalBadge({ action }: { action: string }) {
  if (action === "buy") {
    return (
      <span className="signal-badge signal-buy">
        <TrendingUp size={12} /> BUY
      </span>
    );
  }
  if (action === "sell") {
    return (
      <span className="signal-badge signal-sell">
        <TrendingDown size={12} /> SELL
      </span>
    );
  }
  return <span className="signal-badge signal-hold">HOLD</span>;
}

function ConditionsTable({ context }: { context: any }) {
  if (!context || typeof context !== "object") {
    return null;
  }

  const rows = [
    { label: "Candles disponibles", value: context.candles_count ?? "—", required: context.candles_count != null ? context.candles_count >= (context.ma_long_period ?? 210) + 10 : null },
    { label: "Precio actual", value: context.current_price ?? "—", required: null },
    { label: `MA${context.ma_short_period ?? 9}`, value: context.ma_short_value ?? "—", required: null },
    { label: `MA${context.ma_long_period ?? 200}`, value: context.ma_long_value ?? "—", required: null },
    { label: "Precio > MA200", value: context.price_above_ma200 == null ? "—" : context.price_above_ma200 ? "Sí" : "No", required: context.price_above_ma200 ?? null },
    { label: "Cruce detectado", value: context.crossover ?? "Ninguno", required: context.crossover != null },
    { label: "Posiciones abiertas", value: `${context.open_positions_count ?? 0}/${context.max_positions ?? 2}`, required: (context.open_positions_count ?? 0) < (context.max_positions ?? 2) },
    { label: "Balance disponible", value: context.account_balance != null ? `$${(context.account_balance).toLocaleString()}` : "—", required: null },
    { label: "Riesgo por trade", value: context.risk_per_trade != null ? `${(context.risk_per_trade * 100).toFixed(2)}%` : "—", required: null },
  ];

  return (
    <div className="conditions-table-wrap">
      <h4>Condiciones evaluadas</h4>
      <table className="user-table conditions-table">
        <thead>
          <tr>
            <th>Condición</th>
            <th>Valor</th>
            <th>¿Cumple?</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              <td>{row.label}</td>
              <td>{row.value}</td>
              <td>
                {row.required == null ? (
                  <span className="condition-na">—</span>
                ) : row.required ? (
                  <CheckCircle2 size={14} color="#1f7a57" />
                ) : (
                  <XCircle size={14} color="#a14535" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CycleDetail({ cycle }: { cycle: CycleHistoryEntry }) {
  const [expanded, setExpanded] = useState(false);

  const evalCount = cycle.evaluations?.length ?? 0;
  const tradeCount = cycle.trades?.length ?? 0;
  const adjCount = cycle.adjustments?.length ?? 0;

  return (
    <div className={`cycle-entry ${cycle.status === "error" ? "cycle-error" : ""}`}>
      <div className="cycle-header" onClick={() => setExpanded(!expanded)}>
        <span className="cycle-expand">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span className="cycle-time">{formatTime(cycle.timestamp)}</span>
        <span className={`cycle-source cycle-source-${cycle.source}`}>
          {cycle.source === "auto" ? "Auto" : "Manual"}
        </span>
        <span className="cycle-duration">{formatDuration(cycle.duration_ms)}</span>
        <span className="cycle-stats">
          {cycle.skipped ? (
            <span className="cycle-skipped">Skipped</span>
          ) : (
            <>
              <span className="cycle-stat">{evalCount} eval</span>
              <span className="cycle-stat">{tradeCount} trades</span>
              <span className="cycle-stat">{adjCount} adj</span>
            </>
          )}
        </span>
        {cycle.status === "error" && <XCircle size={14} color="#a14535" />}
      </div>

      {expanded && (
        <div className="cycle-detail">
          {cycle.skipped && (
            <p className="cycle-skipped-msg">
              <AlertCircle size={14} /> Cycle skipped: {cycle.error ?? "Outside trading hours"}
            </p>
          )}

          {cycle.error && !cycle.skipped && (
            <p className="cycle-error-msg">
              <AlertCircle size={14} /> {cycle.error}
            </p>
          )}

          {(!cycle.evaluations || cycle.evaluations.length === 0) && !cycle.skipped && (
            <p className="cycle-skipped-msg">
              <AlertCircle size={14} /> No strategy evaluations in this cycle.
              {cycle.error ? ` Error: ${cycle.error}` : ""}
              {(cycle as any).reason ? ` Reason: ${(cycle as any).reason}` : ""}
            </p>
          )}

          {cycle.evaluations?.length > 0 && (
            <div className="cycle-evaluations">
              <h4>Strategy Evaluations</h4>
              {cycle.evaluations.map((evalItem, idx) => (
                <div key={idx} className="cycle-eval-item">
                  <div className="cycle-eval-header">
                    <strong>{evalItem.strategy_name ?? "Strategy"}</strong>
                    <span className="cycle-eval-symbol">{evalItem.symbol ?? "—"}</span>
                    {evalItem.signal && <SignalBadge action={evalItem.signal.action} />}
                  </div>
                  {evalItem.error && (
                    <p className="cycle-eval-error">
                      <AlertCircle size={12} /> {evalItem.error}
                    </p>
                  )}
                  {evalItem.signal && (
                    <div className="cycle-eval-details">
                      <span>Conf: <strong>{(evalItem.signal.confidence * 100).toFixed(1)}%</strong></span>
                      <span>Entry: <strong>{evalItem.signal.entry_price ?? "—"}</strong></span>
                      <span>SL: <strong>{evalItem.signal.stop_loss ?? "—"}</strong></span>
                      <span>TP: <strong>{evalItem.signal.take_profit ?? "—"}</strong></span>
                      {evalItem.signal.reason && (
                        <span className="cycle-eval-reason">Reason: {evalItem.signal.reason}</span>
                      )}
                    </div>
                  )}
                  {evalItem.signal?.context && <ConditionsTable context={evalItem.signal.context} />}
                  {evalItem.trade_executed && (
                    <p className="cycle-eval-trade">
                      <CheckCircle2 size={12} color="#1f7a57" /> Trade executed
                      {evalItem.trade_result?.position_id ? ` — Position #${evalItem.trade_result.position_id}` : ""}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {cycle.adjustments?.length > 0 && (
            <div className="cycle-adjustments">
              <h4>Adjustments</h4>
              {cycle.adjustments.map((adj, idx) => (
                <div key={idx} className="cycle-adjust-item">
                  <span>Position #{adj.position_id}</span>
                  <span>{adj.action}</span>
                  <span>New SL: {adj.new_stop_loss}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OpenPositionsList({ positions }: { positions: Record<string, OpenPosition[]> }) {
  const userIds = Object.keys(positions);
  if (userIds.length === 0) {
    return <p className="panel-muted">No open positions tracked in memory.</p>;
  }

  return (
    <div className="open-positions">
      {userIds.map((userId) => (
        <div key={userId} className="open-positions-user">
          <h4>User: {userId.slice(0, 8)}…</h4>
          <table className="user-table">
            <thead>
              <tr>
                <th>Position</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Stop Loss</th>
                <th>Take Profit</th>
                <th>Breakeven</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {positions[userId].map((pos) => (
                <tr key={pos.position_id}>
                  <td>#{pos.position_id}</td>
                  <td>
                    {pos.is_buy ? (
                      <span className="signal-badge signal-buy"><TrendingUp size={12} /> BUY</span>
                    ) : (
                      <span className="signal-badge signal-sell"><TrendingDown size={12} /> SELL</span>
                    )}
                  </td>
                  <td>{pos.entry_price}</td>
                  <td>{pos.stop_loss ?? "—"}</td>
                  <td>{pos.take_profit ?? "—"}</td>
                  <td>{pos.breakeven_applied ? <CheckCircle2 size={14} color="#1f7a57" /> : "—"}</td>
                  <td>{formatTime(pos.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

export function BotStatusPage({ session }: BotStatusPageProps) {
  const dispatch = useDispatch();
  const cachedStatus = useSelector((state: RootState) => state.botState.status);
  const cachedCycles = useSelector((state: RootState) => state.botState.cycles);
  const cacheLastUpdated = useSelector((state: RootState) => state.botState.lastUpdated);

  const { data: status, isLoading: statusLoading, isError: statusError } = useGetBotStatusQuery(undefined, {
    pollingInterval: 5000,
  });

  const { data: cyclesData, isLoading: cyclesLoading, isError: cyclesError } = useGetBotCyclesQuery(undefined, {
    pollingInterval: 5000,
  });

  // Cache data in Redux when it arrives from the backend
  useEffect(() => {
    if (status) {
      dispatch(cacheBotStatus(status));
    }
  }, [status, dispatch]);

  useEffect(() => {
    if (cyclesData) {
      dispatch(cacheBotCycles(cyclesData));
    }
  }, [cyclesData, dispatch]);

  // Use cached data as fallback when backend is unavailable
  const effectiveStatus = status ?? cachedStatus;
  const effectiveCycles = cyclesData ?? cachedCycles;
  const usingCache = !status && !!cachedStatus;
  const usingCyclesCache = !cyclesData && !!cachedCycles;

  const [startBot, startResult] = useStartBotMutation();
  const [stopBot, stopResult] = useStopBotMutation();
  const [triggerCycle, cycleResult] = useTriggerCycleMutation();
  const [triggerHealth] = useLazyGetHealthQuery();

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [health, setHealth] = useState<{ service: string; status: string; version: string } | null>(null);

  const addLog = (label: string, status: "loading" | "success" | "error", data?: any, error?: string): number => {
    const id = Date.now() + Math.random();
    setLogs((prev) => [
      { id, label, status, data, error, timestamp: new Date().toLocaleTimeString() },
      ...prev.slice(0, 19),
    ]);
    return id;
  };

  const updateLog = (id: number, status: "success" | "error", data?: any, error?: string) => {
    setLogs((prev) =>
      prev.map((log) =>
        log.id === id
          ? { ...log, status, data, error, timestamp: new Date().toLocaleTimeString() }
          : log
      )
    );
  };

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const result = await triggerHealth().unwrap();
        setHealth(result);
      } catch {
        setHealth(null);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [triggerHealth]);

  const handleStart = async () => {
    const logId = addLog("START BOT", "loading");
    try {
      const data = await startBot().unwrap();
      updateLog(logId, "success", data);
    } catch (err: any) {
      updateLog(logId, "error", null, err?.data?.detail ?? err?.message ?? "Unknown error");
    }
  };

  const handleStop = async () => {
    const logId = addLog("STOP BOT", "loading");
    try {
      const data = await stopBot().unwrap();
      updateLog(logId, "success", data);
    } catch (err: any) {
      updateLog(logId, "error", null, err?.data?.detail ?? err?.message ?? "Unknown error");
    }
  };

  const handleCycle = async () => {
    const logId = addLog("MANUAL CYCLE", "loading");
    try {
      const data = await triggerCycle().unwrap();
      updateLog(logId, "success", data);
    } catch (err: any) {
      updateLog(logId, "error", null, err?.data?.detail ?? err?.message ?? "Unknown error");
    }
  };

  const handleClearCache = () => {
    dispatch(clearBotCache());
    addLog("CACHE CLEARED", "success", { message: "Local cache cleared. Refreshing from backend..." });
  };

  const isRunning = effectiveStatus?.running ?? false;

  return (
    <section className="panel etoro-test-panel">
      <div className="panel-header">
        <Bot size={20} color="#1f7a57" />
        <h2>Trading Bot Control Center</h2>
      </div>

      <p className="etoro-test-subtitle">
        Connected as <strong>{session.name}</strong> &mdash; Trading Core: <code>{tradingCoreUrl}</code>
        {usingCache && (
          <span className="cache-badge">
            <AlertCircle size={12} /> Cached data
          </span>
        )}
        {cacheLastUpdated && (
          <span className="cache-time">Last updated: {new Date(cacheLastUpdated).toLocaleString()}</span>
        )}
        <button className="ghost-button small cache-clear-btn" onClick={handleClearCache}>
          <RefreshCw size={12} /> Clear cache
        </button>
      </p>

      <div className="status-grid" style={{ marginBottom: 24 }}>
        <article>
          <Server size={22} />
          <h2>Service Health</h2>
          {health ? (
            <p className="positive">
              <CheckCircle2 size={16} /> {health.status} — v{health.version}
            </p>
          ) : (
            <p className="negative">
              <XCircle size={16} /> Unreachable
            </p>
          )}
        </article>

        <article>
          <Activity size={22} />
          <h2>Scheduler</h2>
          {statusLoading ? (
            <p><Loader2 size={16} className="spin" /> Loading…</p>
          ) : statusError && !cachedStatus ? (
            <p className="negative"><XCircle size={16} /> Error fetching status</p>
          ) : isRunning ? (
            <p className="positive"><CheckCircle2 size={16} /> Running</p>
          ) : (
            <p><Pause size={16} /> Stopped</p>
          )}
        </article>

        <article>
          <Clock size={22} />
          <h2>Interval</h2>
          <p>{effectiveStatus ? `${effectiveStatus.interval_seconds}s (${Math.round(effectiveStatus.interval_seconds / 60)}min)` : "—"}</p>
        </article>

        <article>
          <Zap size={22} />
          <h2>Cycles Completed</h2>
          <p>{effectiveStatus?.cycles_completed ?? 0}</p>
        </article>
      </div>

      <div className="etoro-test-section" style={{ marginBottom: 24 }}>
        <h3><Bot size={16} /> Bot Controls</h3>
        <div className="etoro-test-card">
          <div className="etoro-test-row" style={{ justifyContent: "flex-start", gap: 10 }}>
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
              <span>Run Cycle Now</span>
            </button>
          </div>
          <p className="field-hint">
            Start: begins automatic trading cycles every {effectiveStatus ? `${Math.round(effectiveStatus.interval_seconds / 60)} minutes` : "5 minutes"}.
            Run Cycle: executes one cycle immediately (useful for testing).
          </p>
        </div>
      </div>

      <div className="etoro-test-section" style={{ marginBottom: 24 }}>
        <h3><Clock size={16} /> Schedule</h3>
        <div className="etoro-test-card">
          <table className="user-table">
            <tbody>
              <tr>
                <td><strong>Last Run</strong></td>
                <td>{formatTime(effectiveStatus?.last_run ?? null)}</td>
              </tr>
              <tr>
                <td><strong>Next Run</strong></td>
                <td>{formatTime(effectiveStatus?.next_run ?? null)}</td>
              </tr>
              <tr>
                <td><strong>Trading Hours</strong></td>
                <td>Sun 5pm ET — Fri 5pm ET (EUR/USD)</td>
              </tr>
              <tr>
                <td><strong>Strategy</strong></td>
                <td>MA200 + MA9 crossover (5m candles)</td>
              </tr>
              <tr>
                <td><strong>Risk per Trade</strong></td>
                <td>0.5% of available balance</td>
              </tr>
              <tr>
                <td><strong>Max Positions</strong></td>
                <td>2 simultaneous</td>
              </tr>
              <tr>
                <td><strong>Breakeven</strong></td>
                <td>Move SL to breakeven at 1.5:1</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="etoro-test-section" style={{ marginBottom: 24 }}>
        <h3>
          <Activity size={16} /> Cycle History
          {isRunning ? (
            <span className="bot-status-badge bot-status-running">
              <CheckCircle2 size={12} /> Running
            </span>
          ) : (
            <span className="bot-status-badge bot-status-stopped">
              <Pause size={12} /> Stopped
            </span>
          )}
        </h3>
        <div className="etoro-test-card">
          {cyclesLoading ? (
            <p><Loader2 size={16} className="spin" /> Loading…</p>
          ) : cyclesError && !cachedCycles ? (
            <p className="negative"><XCircle size={16} /> Error fetching cycles</p>
          ) : !effectiveCycles || effectiveCycles.cycles.length === 0 ? (
            <p className="panel-muted">No cycles yet. Start the bot or run a manual cycle to see activity.</p>
          ) : (
            <div className="cycle-history">
              {usingCyclesCache && (
                <p className="cache-badge"><AlertCircle size={12} /> Showing cached data</p>
              )}
              {effectiveCycles.cycles.map((cycle, idx) => (
                <CycleDetail key={idx} cycle={cycle} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="etoro-test-section" style={{ marginBottom: 24 }}>
        <h3><Zap size={16} /> Open Positions</h3>
        <div className="etoro-test-card">
          {cyclesLoading ? (
            <p><Loader2 size={16} className="spin" /> Loading…</p>
          ) : (
            <OpenPositionsList positions={effectiveCycles?.open_positions ?? {}} />
          )}
        </div>
      </div>

      <div className="etoro-test-log">
        <h3>Activity Log</h3>
        {logs.length === 0 && (
          <p className="panel-muted">No actions yet. Use the controls above to start or test the bot.</p>
        )}
        {logs.map((log) => (
          <div key={log.id} className={`etoro-log-entry etoro-log-${log.status}`}>
            <div className="etoro-log-header">
              <span className="etoro-log-status">
                {log.status === "loading" && <Loader2 size={14} className="spin" />}
                {log.status === "success" && <CheckCircle2 size={14} color="#1f7a57" />}
                {log.status === "error" && <XCircle size={14} color="#a14535" />}
              </span>
              <strong>{log.label}</strong>
              <span className="etoro-log-time">{log.timestamp}</span>
            </div>
            {log.status === "success" && log.data && (
              <pre className="etoro-log-data">{JSON.stringify(log.data, null, 2).slice(0, 3000)}</pre>
            )}
            {log.status === "error" && log.error && (
              <pre className="etoro-log-error">{log.error}</pre>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}