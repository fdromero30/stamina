import { describe, it, expect } from "vitest";
import { routeFromPath, pathFromRoute } from "../routing/routes";

describe("routeFromPath", () => {
  it("returns 'landing' for root path", () => {
    expect(routeFromPath("/")).toBe("landing");
  });

  it("returns 'login' for /login", () => {
    expect(routeFromPath("/login")).toBe("login");
  });

  it("returns 'signup' for /signup", () => {
    expect(routeFromPath("/signup")).toBe("signup");
  });

  it("returns 'dashboard' for /dashboard", () => {
    expect(routeFromPath("/dashboard")).toBe("dashboard");
  });

  it("returns 'strategies' for /strategies", () => {
    expect(routeFromPath("/strategies")).toBe("strategies");
  });

  it("returns 'landing' for unknown paths", () => {
    expect(routeFromPath("/unknown")).toBe("landing");
    expect(routeFromPath("/")).toBe("landing");
  });
});

describe("pathFromRoute", () => {
  it("returns '/' for 'landing'", () => {
    expect(pathFromRoute("landing")).toBe("/");
  });

  it("returns '/login' for 'login'", () => {
    expect(pathFromRoute("login")).toBe("/login");
  });

  it("returns '/signup' for 'signup'", () => {
    expect(pathFromRoute("signup")).toBe("/signup");
  });

  it("returns '/dashboard' for 'dashboard'", () => {
    expect(pathFromRoute("dashboard")).toBe("/dashboard");
  });

  it("returns '/strategies' for 'strategies'", () => {
    expect(pathFromRoute("strategies")).toBe("/strategies");
  });
});