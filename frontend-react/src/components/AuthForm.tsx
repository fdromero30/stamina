import { useMemo, useState, type FormEvent } from "react";
import { ArrowRight, Loader2, LogIn, UserPlus } from "lucide-react";
import type { AuthMode, Session } from "../types";
import { useCreateUserMutation, useGetUsersQuery } from "../store/api";

type AuthFormProps = {
  mode: AuthMode;
  onSubmit: (session: Session) => void;
  onSwitchMode: () => void;
};

export function AuthForm({ mode, onSubmit, onSwitchMode }: AuthFormProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [createUser, { isLoading: isCreating }] = useCreateUserMutation();
  const { data: users, isLoading: isLoadingUsers } = useGetUsersQuery();

  const [apiError, setApiError] = useState<string | null>(null);

  const title = mode === "login" ? "Login" : "Create user";
  const altAction = mode === "login" ? "Create user" : "Login";
  const Icon = mode === "login" ? LogIn : UserPlus;

  const displayName = useMemo(() => {
    if (name.trim()) {
      return name.trim();
    }
    return email.split("@")[0] || "Operator";
  }, [email, name]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (mode === "login") {
      if (!users) {
        setApiError("Unable to reach the server. Try again.");
        return;
      }

      const matched = users.find((u) => u.email === email.trim());
      if (!matched) {
        setApiError("Error while logging in.");
        return;
      }

      onSubmit({ id: matched.id, name: matched.displayName, email: matched.email });
    } else {
      try {
        const created = await createUser({
          email: email.trim(),
          displayName,
        }).unwrap();
        onSubmit({ id: created.id, name: created.displayName, email: created.email });
      } catch (error: any) {
        setApiError(error.data?.message || "Failed to create user.");
      }
    }
  };

  const isBusy = isCreating || isLoadingUsers;

  return (
    <>
      <form className="auth-form" onSubmit={handleSubmit}>
        {mode === "signup" && (
          <label>
            <span>Name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="John Doe"
              autoComplete="name"
            />
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

        {apiError && <p className="form-error">{apiError}</p>}

        <button className="primary-button full" type="submit" disabled={isBusy}>
          {isBusy ? <Loader2 size={18} className="spin" /> : <Icon size={18} />}
          <span>{isBusy ? "Please wait…" : title}</span>
        </button>
      </form>

      <button className="text-button" onClick={onSwitchMode}>
        <span>{altAction}</span>
        <ArrowRight size={16} />
      </button>
    </>
  );
}