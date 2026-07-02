import { Activity, Bot, CheckCircle2, Database, LineChart, Lock, ShieldCheck } from "lucide-react";
import { strategyRows, tradingCoreUrl, usersConfigUrl } from "../data/dashboard";
import type { Session } from "../types";

type DashboardPageProps = {
  session: Session;
  onLogout: () => void;
};

export function DashboardPage({ session, onLogout }: DashboardPageProps) {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={24} />
          <span>Stamina</span>
        </div>
        <nav className="dashboard-nav" aria-label="Dashboard">
          <button className="active">Dashboard</button>
          <button>Strategies</button>
          <button>Users</button>
          <button>Risk</button>
        </nav>
      </aside>

      <section className="workspace">
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
          <div>
            <h2>Next build step</h2>
            <p>
              Connect authenticated users to strategy settings, then let the Python core consume approved configs before sending orders to
              the broker adapter.
            </p>
          </div>
        </section>
      </section>
    </main>
  );
}
