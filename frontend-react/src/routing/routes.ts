export type AppRoute = "landing" | "login" | "signup" | "dashboard";

export function routeFromPath(pathname: string): AppRoute {
  if (pathname === "/login") return "login";
  if (pathname === "/signup") return "signup";
  if (pathname === "/dashboard") return "dashboard";
  return "landing";
}

export function pathFromRoute(route: AppRoute) {
  if (route === "login") return "/login";
  if (route === "signup") return "/signup";
  if (route === "dashboard") return "/dashboard";
  return "/";
}
