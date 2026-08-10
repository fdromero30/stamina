import { useEffect, useState } from "react";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EtoroTestPage } from "./pages/EtoroTestPage";
import { BotStatusPage } from "./pages/BotStatusPage";
import { StrategyChartPage } from "./pages/StrategyChartPage";
import { LandingPage } from "./pages/LandingPage";
import { pathFromRoute, routeFromPath, type AppRoute } from "./routing/routes";
import type { AuthMode, Session } from "./types";

// ── Session persistence (12 hours) ─────────────────────────────────────
const SESSION_STORAGE_KEY = "stamina_session";
const SESSION_TTL_MS = 12 * 60 * 60 * 1000; // 12 hours

type StoredSession = {
  user: Session;
  expiresAt: number;
};

function loadStoredSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    if (!parsed?.user || !parsed?.expiresAt) return null;
    if (Date.now() > parsed.expiresAt) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return parsed.user;
  } catch {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

function saveStoredSession(user: Session) {
  try {
    const stored: StoredSession = {
      user,
      expiresAt: Date.now() + SESSION_TTL_MS,
    };
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(stored));
  } catch {
    // ignore (private mode, etc.)
  }
}

function clearStoredSession() {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromPath(window.location.pathname));
  // Restore session from localStorage so F5 does not log the user out.
  const [session, setSession] = useState<Session | null>(() => loadStoredSession());

  useEffect(() => {
    const handlePopState = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = (nextRoute: AppRoute) => {
    const path = pathFromRoute(nextRoute);
    window.history.pushState({}, "", path);
    setRoute(nextRoute);
  };

  useEffect(() => {
    if ((route === "dashboard" || route === "strategies" || route === "etoro-test" || route === "bot-status" || route === "chart") && !session) {
      window.history.replaceState({}, "", pathFromRoute("login"));
      setRoute("login");
    }
    if (route === "strategies" && session) {
      window.history.replaceState({}, "", pathFromRoute("strategies"));
    }
  }, [route, session]);

  const openDashboard = (user: Session) => {
    saveStoredSession(user);
    setSession(user);
    navigate("dashboard");
  };

  const openStrategies = () => {
    navigate("strategies");
  };

  const openDashboardOrLogin = () => {
    navigate(session ? "dashboard" : "login");
  };

  const openAuthRoute = (mode: AuthMode) => {
    navigate(mode === "login" ? "login" : "signup");
  };

  if ((route === "dashboard" || route === "strategies" || route === "etoro-test" || route === "bot-status" || route === "chart") && session) {
    if (route === "etoro-test") {
      return (
        <DashboardPage
          session={session}
          initialView="dashboard"
          onLogout={() => {
            clearStoredSession();
            setSession(null);
            navigate("landing");
          }}
          overrideContent={<EtoroTestPage session={session} />}
        />
      );
    }

    if (route === "bot-status") {
      return (
        <DashboardPage
          session={session}
          initialView="dashboard"
          onLogout={() => {
            clearStoredSession();
            setSession(null);
            navigate("landing");
          }}
          overrideContent={<BotStatusPage session={session} />}
        />
      );
    }

    if (route === "chart") {
      return (
        <DashboardPage
          session={session}
          initialView="dashboard"
          onLogout={() => {
            clearStoredSession();
            setSession(null);
            navigate("landing");
          }}
          overrideContent={<StrategyChartPage session={session} />}
        />
      );
    }

    return (
      <DashboardPage
        session={session}
        initialView={route === "strategies" ? "strategies" : "dashboard"}
        onLogout={() => {
          clearStoredSession();
          setSession(null);
          navigate("landing");
        }}
      />
    );
  }

  if ((route === "dashboard" || route === "strategies" || route === "etoro-test" || route === "bot-status" || route === "chart") && !session) {
    return null;
  }

  if (route === "login" || route === "signup") {
    const mode: AuthMode = route === "login" ? "login" : "signup";
    const nextMode: AuthMode = mode === "login" ? "signup" : "login";

    return <AuthPage mode={mode} onSubmit={openDashboard} onSwitchMode={() => openAuthRoute(nextMode)} onBack={() => navigate("landing")} />;
  }

  return <LandingPage onLogin={() => navigate("login")} onSignup={() => navigate("signup")} onDashboard={openDashboardOrLogin} />;
}
