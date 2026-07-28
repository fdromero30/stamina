export type AppRoute = "landing" | "login" | "signup" | "dashboard" | "strategies" | "etoro-test";

export function routeFromPath(pathname: string): AppRoute {
  if (pathname === "/login") return "login";
  if (pathname === "/signup") return "signup";
  if (pathname === "/dashboard") return "dashboard";
  if (pathname === "/strategies") return "strategies";
  if (pathname === "/etoro-test") return "etoro-test";
  return "landing";
}

export function pathFromRoute(route: AppRoute) {
  if (route === "login") return "/login";
  if (route === "signup") return "/signup";
  if (route === "dashboard") return "/dashboard";
  if (route === "strategies") return "/strategies";
  if (route === "etoro-test") return "/etoro-test";
  return "/";
}
