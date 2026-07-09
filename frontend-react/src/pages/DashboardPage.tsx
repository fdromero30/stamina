import { useState } from "react";
import { Activity, Bot, CheckCircle2, Database, Key, LineChart, Loader2, Lock, ShieldCheck, Users } from "lucide-react";
import { strategyRows, tradingCoreUrl, usersConfigUrl } from "../data/dashboard";
import { useGetUsersQuery } from "../store/api";
import type { Session } from "../types";
import { ApiKeysPage } from "./ApiKeysPage";

type DashboardPageProps = {
  session: Session;
  onLogout: () => void;
};

type DashboardView = "dashboard" | "apikeys";

export function DashboardPage({ session, onLogout }: DashboardPageProps) {
  const [view, setView] = useState<DashboardView>("dashboard");
  const { data: apiUsers, isLoading, isError } = useGetUsersQuery();

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={24} />
          <span>Stamina</span>
        </div>
        <nav className="dashboard-nav" aria-label="Dashboard">
          <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>Dashboard</button>
          <button>Strategies</button>
          <button>Users</button>
          <button>Risk</button>
          <button className={view === "apikeys" ? "active" : ""} onClick={() => setView("apikeys")}>
            <Key size={16} />
            <span>API Keys</span>
          </button>
        </nav>
      </aside>

      <section className="workspace">
        {view === "apikeys" ? (
          <ApiKeysPage session={session} />
        ) : (
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
        )}
      </section>
    </main>
  );
}
