import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Server,
  XCircle,
  Zap,
} from "lucide-react";
import { tradingCoreUrl } from "../data/dashboard";
import {
  useGetBotStatusQuery,
  useStartBotMutation,
  useStopBotMutation,
  useTriggerCycleMutation,
  useLazyGetHealthQuery,
} from "../store/botApi";
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

export function BotStatusPage({ session }: BotStatusPageProps) {
  const { data: status, isLoading: statusLoading, isError: statusError } = useGetBotStatusQuery(undefined, {
    pollingInterval: 5000,
  });

  const [startBot, startResult] = useStartBotMutation();
  const [stopBot, stopResult] = useStopBotMutation();
  const [triggerCycle, cycleResult] = useTriggerCycleMutation();
  const [triggerHealth] = useLazyGetHealthQuery();

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [health, setHealth] = useState<{ service: string; status: string; version: string } | null>(null);
  const [logCounter, setLogCounter] = useState(0);

  const addLog = (label: string, status: "loading" | "success" | "error", data?: any, error?: string) => {
    setLogCounter((c) => c + 1);
    setLogs((prev) => [
      { id: logCounter, label, status, data, error, timestamp: new Date().toLocaleTimeString() },
      ...prev.slice(0, 19),
    ]);
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
    addLog("START BOT", "loading");
    try {
      const data = await startBot().unwrap();
      addLog("START BOT", "success", data);
    } catch (err: any) {
      addLog("START BOT", "error", null, err?.data?.detail ?? err?.message ?? "Unknown error");
    }
  };

  const handleStop = async () => {
    addLog("STOP BOT", "loading");
    try {
      const data = await stopBot().unwrap();
      addLog("STOP BOT", "success", data);
    } catch (err: any) {
      addLog("STOP BOT", "error", null, err?.data?.detail ?? err?.message ?? "Unknown error");
    }
  };

  const handleCycle = async () => {
    addLog("MANUAL CYCLE", "loading");
    try {
      const data = await triggerCycle().unwrap();
      addLog("MANUAL CYCLE", "success", data);
    } catch (err: any) {
      addLog("MANUAL CYCLE", "error", null, err?.data?.detail ?? err?.message ?? "Unknown error");
    }
  };

  const formatTime = (iso: string | null) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  const isRunning = status?.running ?? false;

  return (
    <section className="panel etoro-test-panel">
      <div className="panel-header">
        <Bot size={20} color="#1f7a57" />
        <h2>Trading Bot Control Center</h2>
      </div>

      <p className="etoro-test-subtitle">
        Connected as <strong>{session.name}</strong> &mdash; Trading Core: <code>{tradingCoreUrl}</code>
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
          ) : statusError ? (
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
          <p>{status ? `${status.interval_seconds}s (${Math.round(status.interval_seconds / 60)}min)` : "—"}</p>
        </article>

        <article>
          <Zap size={22} />
          <h2>Cycles Completed</h2>
          <p>{status?.cycles_completed ?? 0}</p>
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
            Start: begins automatic trading cycles every {status ? `${Math.round(status.interval_seconds / 60)} minutes` : "5 minutes"}.
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
                <td>{formatTime(status?.last_run ?? null)}</td>
              </tr>
              <tr>
                <td><strong>Next Run</strong></td>
                <td>{formatTime(status?.next_run ?? null)}</td>
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