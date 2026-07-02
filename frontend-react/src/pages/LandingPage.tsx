import { ArrowRight, Bot, LogIn, ShieldCheck, UserPlus, Users } from "lucide-react";
import { BrandButton } from "../components/BrandButton";

type LandingPageProps = {
  onLogin: () => void;
  onSignup: () => void;
  onDashboard: () => void;
};

export function LandingPage({ onLogin, onSignup, onDashboard }: LandingPageProps) {
  return (
    <main className="landing-shell">
      <nav className="landing-nav" aria-label="Primary">
        <BrandButton onClick={onDashboard} label="Open Stamina dashboard" />
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
