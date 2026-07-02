import { LogIn, UserPlus } from "lucide-react";
import { AuthForm } from "../components/AuthForm";
import { BrandButton } from "../components/BrandButton";
import type { AuthMode, Session } from "../types";

type AuthPageProps = {
  mode: AuthMode;
  onSubmit: (session: Session) => void;
  onSwitchMode: () => void;
  onBack: () => void;
};

export function AuthPage({ mode, onSubmit, onSwitchMode, onBack }: AuthPageProps) {
  const title = mode === "login" ? "Login" : "Create user";
  const Icon = mode === "login" ? LogIn : UserPlus;

  return (
    <main className="auth-shell">
      <BrandButton className="floating-brand" onClick={onBack} label="Back to Stamina landing" />

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

        <AuthForm mode={mode} onSubmit={onSubmit} onSwitchMode={onSwitchMode} />
      </section>
    </main>
  );
}
