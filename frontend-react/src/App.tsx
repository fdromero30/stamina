import { useEffect, useState } from "react";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
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
    if (route === "dashboard" && !session) {
      window.history.replaceState({}, "", pathFromRoute("login"));
      setRoute("login");
    }
  }, [route, session]);

  const openDashboard = (user: Session) => {
    setSession(user);
    navigate("dashboard");
  };

  const openDashboardOrLogin = () => {
    navigate(session ? "dashboard" : "login");
  };

  const openAuthRoute = (mode: AuthMode) => {
    navigate(mode === "login" ? "login" : "signup");
  };

  if (route === "dashboard" && session) {
    return (
      <DashboardPage
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

  if (route === "login" || route === "signup") {
    const mode: AuthMode = route === "login" ? "login" : "signup";
    const nextMode: AuthMode = mode === "login" ? "signup" : "login";

    return <AuthPage mode={mode} onSubmit={openDashboard} onSwitchMode={() => openAuthRoute(nextMode)} onBack={() => navigate("landing")} />;
  }

  return <LandingPage onLogin={() => navigate("login")} onSignup={() => navigate("signup")} onDashboard={openDashboardOrLogin} />;
}
