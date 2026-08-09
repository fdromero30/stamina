import { useEffect, useState } from "react";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EtoroTestPage } from "./pages/EtoroTestPage";
import { BotStatusPage } from "./pages/BotStatusPage";
import { StrategyChartPage } from "./pages/StrategyChartPage";
import { LandingPage } from "./pages/LandingPage";
import { pathFromRoute, routeFromPath, type AppRoute } from "./routing/routes";
import type { AuthMode, Session } from "./types";

export function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromPath(window.location.pathname));
  const [session, setSession] = useState<Session | null>(null);

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
