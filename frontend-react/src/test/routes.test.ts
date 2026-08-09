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

  it("returns 'etoro-test' for /etoro-test", () => {
    expect(routeFromPath("/etoro-test")).toBe("etoro-test");
  });

  it("returns 'bot-status' for /bot-status", () => {
    expect(routeFromPath("/bot-status")).toBe("bot-status");
  });

  it("returns 'chart' for /chart", () => {
    expect(routeFromPath("/chart")).toBe("chart");
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

  it("returns '/etoro-test' for 'etoro-test'", () => {
    expect(pathFromRoute("etoro-test")).toBe("/etoro-test");
  });

  it("returns '/bot-status' for 'bot-status'", () => {
    expect(pathFromRoute("bot-status")).toBe("/bot-status");
  });

  it("returns '/chart' for 'chart'", () => {
    expect(pathFromRoute("chart")).toBe("/chart");
  });
});
