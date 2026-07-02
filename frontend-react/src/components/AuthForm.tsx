import { useMemo, useState, type FormEvent } from "react";
import { ArrowRight, LogIn, UserPlus } from "lucide-react";
import type { AuthMode, Session } from "../types";

type AuthFormProps = {
  mode: AuthMode;
  onSubmit: (session: Session) => void;
  onSwitchMode: () => void;
};

export function AuthForm({ mode, onSubmit, onSwitchMode }: AuthFormProps) {
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit({ name: displayName, email: email.trim() });
  };

  return (
    <>
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
    </>
  );
}
