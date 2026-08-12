import { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Loader2,
  TrendingDown,
  TrendingUp,
  XCircle,
} from "lucide-react";
import {
  useGetBotCyclesQuery,
  type BotRun,
  type CycleHistoryEntry,
  type OpenPosition,
} from "../store/botApi";

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

export function SignalBadge({ action }: { action: string }) {
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

export function FeedDiagnostics({ diag }: { diag: any }) {
  if (!diag || typeof diag !== "object") {
    return null;
  }

  const age = diag.last_candle_age_seconds;
  const hasExcludedCross = diag.last_crosses_up || diag.last_crosses_down;
  const hasEvaluatedCross = diag.evaluated_crosses_up || diag.evaluated_crosses_down;
  const feedStale = age != null && age > 300;

  return (
    <div className="feed-diagnostics">
      <h4>Feed / Diagnóstico</h4>
      <table className="user-table conditions-table feed-diag-table">
        <tbody>
          <tr>
            <td>Vela evaluación (2ª última)</td>
            <td>{diag.penultimate_candle_time ?? "—"}</td>
          </tr>
          <tr>
            <td>Vela excluida (última)</td>
            <td>{diag.last_candle_time ?? "—"}</td>
          </tr>
          <tr>
            <td>Edad vela excluida</td>
            <td className={feedStale ? "diag-warn" : ""}>
              {age != null ? `${age}s${feedStale ? " ⚠ >300s (vela cerrada descartada)" : ""}` : "—"}
            </td>
          </tr>
          <tr>
            <td>Cruce en vela excluida</td>
            <td className={hasExcludedCross ? "diag-warn" : ""}>
              {hasExcludedCross
                ? `⚠ up=${diag.last_crosses_up ? "Sí" : "No"}, down=${diag.last_crosses_down ? "Sí" : "No"}`
                : "No"}
            </td>
          </tr>
          <tr>
            <td>Cruce en vela evaluada</td>
            <td>
              {hasEvaluatedCross
                ? `up=${diag.evaluated_crosses_up ? "Sí" : "No"}, down=${diag.evaluated_crosses_down ? "Sí" : "No"}`
                : "No"}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function ConditionsTable({ context }: { context: any }) {
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
      {context.feed_diagnostics && (
        <FeedDiagnostics diag={context.feed_diagnostics} />
      )}
    </div>
  );
}

export function CycleDetail({ cycle }: { cycle: CycleHistoryEntry }) {
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

export function OpenPositionsList({ positions }: { positions: Record<string, OpenPosition[]> }) {
  const userIds = Object.keys(positions);
  if (userIds.length === 0) {
    return <p className="panel-muted">No open positions tracked in memory.</p>;
  }

  return (
    <div className="open-positions-scroll">
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
    </div>
  );
}

/**
 * A single bot execution (start → stop) with its cycles nested inside.
 * Collapsible so long histories stay readable.
 */
function RunGroup({ run }: { run: BotRun }) {
  const [expanded, setExpanded] = useState(false);
  const cycles = run.cycles ?? [];
  const statusLabel =
    run.status === "running"
      ? "Running"
      : run.status === "stopped"
        ? "Stopped"
        : run.status === "crashed"
          ? "Crashed"
          : run.status;
  const statusClass =
    run.status === "running"
      ? "cycle-run-status cycle-run-running"
      : run.status === "crashed"
        ? "cycle-run-status cycle-run-crashed"
        : "cycle-run-status cycle-run-stopped";

  return (
    <div className="cycle-run-group">
      <div className="cycle-run-header" onClick={() => setExpanded(!expanded)}>
        <span className="cycle-expand">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span className="cycle-run-id">Run #{run.id.slice(0, 8)}</span>
        <span className="cycle-run-time">
          {formatTime(run.started_at)}
          {run.stopped_at ? ` → ${formatTime(run.stopped_at)}` : ""}
        </span>
        <span className={statusClass}>{statusLabel}</span>
        <span className="cycle-run-cycles">{cycles.length} cycles</span>
      </div>
      {expanded && (
        <div className="cycle-run-body">
          {cycles.length === 0 && (
            <p className="panel-muted">No cycles recorded in this run.</p>
          )}
          {cycles.map((cycle, idx) => (
            <CycleDetail key={cycle.timestamp + idx} cycle={cycle} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Full-cycle log panel with internal scroll.
 * Groups cycles by bot execution (run), most recent first.
 */
export function CycleLog() {
  const { data: cyclesData, isLoading, isError } = useGetBotCyclesQuery(undefined, {
    pollingInterval: 5000,
  });

  // Resizable height (same pattern as the chart panel)
  const [logHeight, setLogHeight] = useState(480);
  const panelRef = useRef<HTMLDivElement>(null);

  // Drag-to-resize height (vertical)
  const handleResizeDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = logHeight;
    const onMouseMove = (ev: MouseEvent) => {
      const deltaY = ev.clientY - startY;
      const nextHeight = Math.min(900, Math.max(220, startHeight + deltaY));
      setLogHeight(nextHeight);
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

  const runs = cyclesData?.runs ?? [];
  const recentCycles = cyclesData?.recent_cycles ?? [];
  const totalCycles = runs.reduce((sum, run) => sum + (run.cycles?.length ?? 0), 0) + recentCycles.length;

  return (
    <div className="cycle-log-panel" ref={panelRef} style={{ height: logHeight }}>
      <div className="cycle-log-header">
        <h3>Cycle Log</h3>
        <span className="cycle-log-count">
          {runs.length > 0 ? `${runs.length} runs · ${totalCycles} cycles` : `${totalCycles} cycles`}
        </span>
      </div>
      <div className="cycle-log-scroll">
        {isLoading && (
          <p className="panel-muted">
            <Loader2 size={16} className="spin" /> Loading cycles…
          </p>
        )}
        {isError && (
          <p className="panel-muted">
            <XCircle size={16} color="#a14535" /> Error fetching cycles
          </p>
        )}
        {!isLoading && !isError && runs.length === 0 && recentCycles.length === 0 && (
          <p className="panel-muted">No cycles yet. Start the bot or run a manual cycle to see activity.</p>
        )}
        {!isLoading && !isError && runs.length > 0 && (
          <div className="cycle-history">
            {runs.map((run) => (
              <RunGroup key={run.id} run={run} />
            ))}
          </div>
        )}
        {!isLoading && !isError && runs.length === 0 && recentCycles.length > 0 && (
          <div className="cycle-history">
            {recentCycles.map((cycle, idx) => (
              <CycleDetail key={cycle.timestamp + idx} cycle={cycle} />
            ))}
          </div>
        )}
      </div>
      {/* Drag handle para redimensionar la altura */}
      <div
        className="cycle-log-resize-handle"
        onMouseDown={handleResizeDragStart}
        title="Arrastra para redimensionar la altura del log"
      >
        <span>⠿</span>
      </div>
    </div>
  );
}
