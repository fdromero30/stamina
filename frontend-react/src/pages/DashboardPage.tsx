import { useState } from "react";
import { Activity, AlertCircle, Bot, CheckCircle2, Database, Key, LineChart, Loader2, Lock, ShieldCheck, TrendingUp, TrendingDown, Users, XCircle, Pause } from "lucide-react";
import { strategyRows, tradingCoreUrl, usersConfigUrl } from "../data/dashboard";
import { useGetUsersQuery } from "../store/api";
import { useGetBotCyclesQuery, useGetBotStatusQuery } from "../store/botApi";
import type { Session } from "../types";
import type { ReactNode } from "react";
import { ApiKeysPage } from "./ApiKeysPage";
import { EtoroTestPage } from "./EtoroTestPage";
import { BotStatusPage } from "./BotStatusPage";
import { StrategyChartPage } from "./StrategyChartPage";
import { StrategiesPage } from "./StrategiesPage";

type DashboardPageProps = {
  session: Session;
  initialView?: DashboardView;
  onLogout: () => void;
  overrideContent?: ReactNode;
};

type DashboardView = "dashboard" | "apikeys" | "strategies" | "etoro-test" | "bot-status" | "chart";

export function DashboardPage({ session, initialView = "dashboard", onLogout, overrideContent }: DashboardPageProps) {
  const [view, setView] = useState<DashboardView>(initialView);
  const { data: apiUsers, isLoading, isError } = useGetUsersQuery();
  const { data: botStatus } = useGetBotStatusQuery(undefined, { pollingInterval: 5000 });
  const { data: botCycles } = useGetBotCyclesQuery(undefined, { pollingInterval: 5000 });

  const lastCycle = botCycles?.cycles?.[0];
  const lastEvaluation = lastCycle?.evaluations?.[0];
  const signal = lastEvaluation?.signal;
  const ctx = signal?.context;
  const isRunning = botStatus?.running ?? false;
  const positionLimitOk = ctx ? (ctx.open_positions_count ?? 0) < (ctx.max_positions ?? 2) : null;
  const candlesOk = ctx ? (ctx.candles_count ?? 0) >= (ctx.ma_long_period ?? 210) + 10 : null;
  const crossoverOk = ctx ? (ctx.crossover != null) : null;
  const trendOk = ctx ? (ctx.price_above_ma200 != null) : null;
  const whyNoTrade = signal && !lastEvaluation?.trade_executed ? signal.reason : null;

  const renderWorkspace = () => {
    if (overrideContent) return overrideContent;

    switch (view) {
      case "apikeys":
        return <ApiKeysPage session={session} />;
      case "strategies":
        return <StrategiesPage session={session} />;
      case "etoro-test":
        return <EtoroTestPage session={session} />;
      case "bot-status":
        return <BotStatusPage session={session} />;
      case "chart":
        return <StrategyChartPage session={session} />;
      default:
        return (
          <>
            <header className="topbar">
              <div>
                <p className="eyebrow">Trading operations</p>
                <h1>Bot control center</h1>
                <p className="welcome">Welcome, {session.name}</p>
              </div>
              <div className="topbar-actions">
                <button className="secondary-button">
                  <LineChart size={18} />
                  <span>Create strategy</span>
                </button>
                <button className="ghost-button dark" onClick={onLogout}>
                  <Lock size={18} />
                  <span>Logout</span>
                </button>
              </div>
            </header>

            <section className="status-grid">
              <article>
                <Bot size={22} />
                <h2>Trading Core</h2>
                <p>{tradingCoreUrl}</p>
              </article>
              <article>
                <Database size={22} />
                <h2>Users API</h2>
                <p>{usersConfigUrl}</p>
              </article>
              <article>
                <ShieldCheck size={22} />
                <h2>Risk Mode</h2>
                <p>Paper trading first</p>
              </article>
            </section>

            <section className="panel bot-last-activity">
              <div className="panel-header">
                <Bot size={20} color="#1f7a57" />
                <h2>Última actividad del bot</h2>
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

              {!lastCycle ? (
                <p className="panel-muted">No cycles yet. Start the bot on the Bot Status page to see activity.</p>
              ) : (
                <div className="bot-last-activity-content">
                  <div className="bot-last-activity-meta">
                    <span><strong>Último ciclo:</strong> {new Date(lastCycle.timestamp).toLocaleString()}</span>
                    <span className={`cycle-source cycle-source-${lastCycle.source}`}>
                      {lastCycle.source === "auto" ? "Auto" : "Manual"}
                    </span>
                    {lastCycle.skipped && <span className="cycle-skipped">Cycle skipped</span>}
                  </div>

                  {lastEvaluation && (
                    <div className="bot-last-eval">
                      <div className="bot-last-eval-header">
                        <strong>{lastEvaluation.strategy_name ?? "Strategy"}</strong>
                        <span className="cycle-eval-symbol">{lastEvaluation.symbol ?? "—"}</span>
                        {signal && (
                          signal.action === "buy" ? (
                            <span className="signal-badge signal-buy"><TrendingUp size={12} /> BUY</span>
                          ) : signal.action === "sell" ? (
                            <span className="signal-badge signal-sell"><TrendingDown size={12} /> SELL</span>
                          ) : (
                            <span className="signal-badge signal-hold">HOLD</span>
                          )
                        )}
                        {lastEvaluation.trade_executed && (
                          <span className="cycle-eval-trade">Trade executed</span>
                        )}
                      </div>

                      {ctx && (
                        <div className="bot-last-conditions">
                          <div className="bot-last-cond-row">
                            <span className={candlesOk === false ? "condition-fail" : "condition-ok"}>
                              {candlesOk === true ? <CheckCircle2 size={12} color="#1f7a57" /> : candlesOk === false ? <XCircle size={12} color="#a14535" /> : null}
                              Velas: {ctx.candles_count ?? "—"} / mín {(ctx.ma_long_period ?? 210) + 10}
                            </span>
                            <span className={trendOk === false ? "condition-fail" : "condition-ok"}>
                              {trendOk === true ? <CheckCircle2 size={12} color="#1f7a57" /> : trendOk === false ? <XCircle size={12} color="#a14535" /> : null}
                              Precio: {ctx.current_price ?? "—"} · MA{(ctx.ma_long_period ?? 200)}: {ctx.ma_long_value ?? "—"}
                            </span>
                            <span className={crossoverOk === false ? "condition-fail" : "condition-ok"}>
                              {crossoverOk === true ? <CheckCircle2 size={12} color="#1f7a57" /> : crossoverOk === false ? <XCircle size={12} color="#a14535" /> : null}
                              Cruce: {ctx.crossover ?? "Ninguno"}
                            </span>
                            <span className={positionLimitOk === false ? "condition-fail" : "condition-ok"}>
                              {positionLimitOk === true ? <CheckCircle2 size={12} color="#1f7a57" /> : positionLimitOk === false ? <XCircle size={12} color="#a14535" /> : null}
                              Posiciones: {ctx.open_positions_count ?? 0}/{ctx.max_positions ?? 2}
                            </span>
                          </div>

                          <div className="bot-last-values">
                            <span>MA{ctx.ma_short_period ?? 9}: <strong>{ctx.ma_short_value ?? "—"}</strong></span>
                            <span>MA{ctx.ma_long_period ?? 200}: <strong>{ctx.ma_long_value ?? "—"}</strong></span>
                            <span>Bid: <strong>{ctx.bid ?? "—"}</strong></span>
                            <span>Ask: <strong>{ctx.ask ?? "—"}</strong></span>
                            <span>Balance: <strong>${(ctx.account_balance ?? 0).toLocaleString()}</strong></span>
                            <span>Riesgo: <strong>{((ctx.risk_per_trade ?? 0) * 100).toFixed(2)}%</strong></span>
                          </div>
                        </div>
                      )}

                      {whyNoTrade && (
                        <p className="bot-last-reason">
                          <AlertCircle size={14} /> {whyNoTrade}
                        </p>
                      )}
                      {signal?.reason && (
                        <p className="bot-last-reason">
                          <CheckCircle2 size={14} color="#1f7a57" /> {signal.reason}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>

            <section className="strategy-table" aria-label="Strategy status">
              <div className="table-header">
                <h2>Strategy status</h2>
                <button className="primary-button">
                  <CheckCircle2 size={18} />
                  <span>Sync configs</span>
                </button>
              </div>
              <div className="table-rows">
                {strategyRows.map((row) => (
                  <article key={row.name} className="strategy-row">
                    <strong>{row.name}</strong>
                    <span>{row.status}</span>
                    <span>{row.risk}</span>
                    <span className={row.pnl.startsWith("+") ? "positive" : "negative"}>{row.pnl}</span>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <Users size={20} />
                <h2>Registered users</h2>
              </div>
              {isLoading && (
                <p className="panel-muted">
                  <Loader2 size={16} className="spin" /> Loading users…
                </p>
              )}
              {isError && <p className="panel-muted">Could not load users from API.</p>}
              {apiUsers && apiUsers.length === 0 && <p className="panel-muted">No users registered yet.</p>}
              {apiUsers && apiUsers.length > 0 && (
                <table className="user-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apiUsers.map((u) => (
                      <tr key={u.id}>
                        <td>{u.displayName}</td>
                        <td>{u.email}</td>
                        <td>{new Date(u.createdAt).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </>
        );
    }
  };

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={24} />
          <span>Stamina</span>
        </div>
        <nav className="dashboard-nav" aria-label="Dashboard">
          <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>Dashboard</button>
          <button className={view === "strategies" ? "active" : ""} onClick={() => setView("strategies")}>Strategies</button>
          <button>Users</button>
          <button>Risk</button>
          <button className={view === "apikeys" ? "active" : ""} onClick={() => setView("apikeys")}>
            <Key size={16} />
            <span>API Keys</span>
          </button>
          <button className={view === "etoro-test" ? "active" : ""} onClick={() => setView("etoro-test")}>
            <Activity size={16} />
            <span>eToro Test</span>
          </button>
          <button className={view === "bot-status" ? "active" : ""} onClick={() => setView("bot-status")}>
            <Bot size={16} />
            <span>Bot Status</span>
          </button>
          <button className={view === "chart" ? "active" : ""} onClick={() => setView("chart")}>
            <LineChart size={16} />
            <span>Strategy Chart</span>
          </button>
        </nav>
      </aside>

      <section className="workspace">
        {renderWorkspace()}
      </section>
    </main>
  );
}