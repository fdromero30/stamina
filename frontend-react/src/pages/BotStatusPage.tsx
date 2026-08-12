import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
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
import { cacheBotStatus, clearBotCache } from "../store/botStateSlice";
import type { RootState } from "../store/store";
import type { Session } from "../types";

type BotStatusPageProps = {
  session: Session;
};

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function BotStatusPage({ session }: BotStatusPageProps) {
  const dispatch = useDispatch();
  const cachedStatus = useSelector((state: RootState) => state.botState.status);
  const cacheLastUpdated = useSelector((state: RootState) => state.botState.lastUpdated);

  const { data: status, isLoading: statusLoading, isError: statusError } = useGetBotStatusQuery(undefined, {
    pollingInterval: 5000,
  });

  // Cache data in Redux when it arrives from the backend
  useEffect(() => {
    if (status) {
      dispatch(cacheBotStatus(status));
    }
  }, [status, dispatch]);

  // Use cached data as fallback when backend is unavailable
  const effectiveStatus = status ?? cachedStatus;
  const usingCache = !status && !!cachedStatus;

  const [startBot, startResult] = useStartBotMutation();
  const [stopBot, stopResult] = useStopBotMutation();
  const [triggerCycle, cycleResult] = useTriggerCycleMutation();
  const [triggerHealth] = useLazyGetHealthQuery();

  const [health, setHealth] = useState<{ service: string; status: string; version: string } | null>(null);

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
    try {
      await startBot().unwrap();
    } catch {
      // ignore
    }
  };

  const handleStop = async () => {
    try {
      await stopBot().unwrap();
    } catch {
      // ignore
    }
  };

  const handleCycle = async () => {
    try {
      await triggerCycle().unwrap();
    } catch {
      // ignore
    }
  };

  const handleClearCache = () => {
    dispatch(clearBotCache());
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
              <tr>
                <td><strong>Next News Blackout</strong></td>
                <td>
                  {effectiveStatus?.next_blackout ? (
                    <>
                      {effectiveStatus.next_blackout.title} ({effectiveStatus.next_blackout.country}) —{" "}
                      {formatTime(effectiveStatus.next_blackout.event_time)}{" "}
                      <span className="field-hint" style={{ display: "inline" }}>
                        (bot pausa 30 min antes / 30 min después)
                      </span>
                    </>
                  ) : (
                    "No hay eventos High EUR/USD programados"
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}