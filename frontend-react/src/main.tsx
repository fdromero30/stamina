import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  LineChart,
  Lock,
  LogIn,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import "./styles.css";

const tradingCoreUrl = import.meta.env.VITE_TRADING_CORE_URL ?? "http://localhost:8000";
const usersConfigUrl = import.meta.env.VITE_USERS_CONFIG_API_URL ?? "http://localhost:8080";

type Route = "landing" | "login" | "signup" | "dashboard";

type Session = {
  name: string;
  email: string;
};

const strategyRows = [
  { name: "Momentum BTC", status: "Paper", risk: "2.1%", pnl: "+4.8%" },
  { name: "ETH Mean Reversion", status: "Review", risk: "1.4%", pnl: "+1.2%" },
  { name: "Index Hedge", status: "Live guard", risk: "0.8%", pnl: "-0.3%" },
];

function App() {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname));
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    const handlePopState = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (nextRoute: Route) => {
    const path = pathFromRoute(nextRoute);
    window.history.pushState({}, "", path);
    setRoute(nextRoute);
  };

  useEffect(() => {
    if (route === "dashboard" && !session) {
      window.history.replaceState({}, "", "/login");
      setRoute("login");
    }
  }, [route, session]);

  const openDashboard = (user: Session) => {
    setSession(user);
    navigate("dashboard");
  };

  const goToDashboard = () => {
    if (session) {
      navigate("dashboard");
      return;
    }

    navigate("login");
  };

  if (route === "dashboard" && session) {
    return (
      <Dashboard
        session={session}
        onLogout={() => {
          setSession(null);
          navigate("landing");
        }}
      />
    );
  }

  if (route === "dashboard" && !session) {
    return null;
  }

  if (route === "login") {
    return (
      <AuthLayout mode="login" onSubmit={openDashboard} onSwitchMode={() => navigate("signup")} onBack={() => navigate("landing")} />
    );
  }

  if (route === "signup") {
    return (
      <AuthLayout mode="signup" onSubmit={openDashboard} onSwitchMode={() => navigate("login")} onBack={() => navigate("landing")} />
    );
  }

  return <Landing onLogin={() => navigate("login")} onSignup={() => navigate("signup")} onDashboard={goToDashboard} />;
}

function routeFromPath(pathname: string): Route {
  if (pathname === "/login") return "login";
  if (pathname === "/signup") return "signup";
  if (pathname === "/dashboard") return "dashboard";
  return "landing";
}

function pathFromRoute(route: Route) {
  if (route === "login") return "/login";
  if (route === "signup") return "/signup";
  if (route === "dashboard") return "/dashboard";
  return "/";
}

type LandingProps = {
  onLogin: () => void;
  onSignup: () => void;
  onDashboard: () => void;
};

function Landing({ onLogin, onSignup, onDashboard }: LandingProps) {
  return (
    <main className="landing-shell">
      <nav className="landing-nav" aria-label="Primary">
        <button className="brand-button" onClick={onDashboard} aria-label="Open Stamina dashboard">
          <Activity size={24} />
          <span>Stamina</span>
        </button>
        <div className="nav-actions">
          <button className="ghost-button" onClick={onLogin}>
            <LogIn size={18} />
            <span>Login</span>
          </button>
          <button className="primary-button" onClick={onSignup}>
            <UserPlus size={18} />
            <span>Create user</span>
          </button>
        </div>
      </nav>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Trading operations</p>
          <h1>Stamina</h1>
          <p className="hero-text">
            Control strategies, users, risk limits, and bot infrastructure from one focused operating surface.
          </p>
          <div className="hero-actions">
            <button className="primary-button large" onClick={onLogin}>
              <LogIn size={19} />
              <span>Access dashboard</span>
            </button>
            <button className="secondary-button large" onClick={onSignup}>
              <UserPlus size={19} />
              <span>Create account</span>
            </button>
          </div>
        </div>

        <div className="hero-console" aria-label="Dashboard preview">
          <div className="console-header">
            <span />
            <span />
            <span />
          </div>
          <div className="console-grid">
            <article>
              <Bot size={21} />
              <strong>Trading Core</strong>
              <span>Online</span>
            </article>
            <article>
              <Users size={21} />
              <strong>Users API</strong>
              <span>Ready</span>
            </article>
            <article>
              <ShieldCheck size={21} />
              <strong>Risk Mode</strong>
              <span>Paper first</span>
            </article>
          </div>
          <div className="signal-panel">
            <div>
              <span>Approved configs</span>
              <strong>18</strong>
            </div>
            <ArrowRight size={18} />
            <div>
              <span>Broker adapter</span>
              <strong>Guarded</strong>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

type AuthLayoutProps = {
  mode: "login" | "signup";
  onSubmit: (session: Session) => void;
  onSwitchMode: () => void;
  onBack: () => void;
};

function AuthLayout({ mode, onSubmit, onSwitchMode, onBack }: AuthLayoutProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const title = mode === "login" ? "Login" : "Create user";
  const altAction = mode === "login" ? "Create user" : "Login";
  const Icon = mode === "login" ? LogIn : UserPlus;

  const displayName = useMemo(() => {
    if (name.trim()) {
      return name.trim();
    }

    return email.split("@")[0] || "Operator";
  }, [email, name]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit({ name: displayName, email: email.trim() });
  };

  return (
    <main className="auth-shell">
      <button className="brand-button floating-brand" onClick={onBack} aria-label="Back to Stamina landing">
        <Activity size={24} />
        <span>Stamina</span>
      </button>

      <section className="auth-panel">
        <div className="auth-intro">
          <span className="auth-icon">
            <Icon size={24} />
          </span>
          <p className="eyebrow">Secure access</p>
          <h1>{title}</h1>
          <p>
            {mode === "login"
              ? "Enter with your operator account and continue to the control center."
              : "Create an operator profile to start managing trading configuration."}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "signup" && (
            <label>
              <span>Name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Fabian Romero" autoComplete="name" />
            </label>
          )}
          <label>
            <span>Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="operator@stamina.local"
              autoComplete="email"
            />
          </label>
          <label>
            <span>Password</span>
            <input
              required
              minLength={6}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>
          <button className="primary-button full" type="submit">
            <Icon size={18} />
            <span>{title}</span>
          </button>
        </form>

        <button className="text-button" onClick={onSwitchMode}>
          <span>{altAction}</span>
          <ArrowRight size={16} />
        </button>
      </section>
    </main>
  );
}

type DashboardProps = {
  session: Session;
  onLogout: () => void;
};

function Dashboard({ session, onLogout }: DashboardProps) {
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

createRoot(document.getElementById("root")!).render(<App />);
