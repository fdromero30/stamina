export type AuthMode = "login" | "signup";

export type Session = {
  name: string;
  email: string;
};

export type StrategyRow = {
  name: string;
  status: string;
  risk: string;
  pnl: string;
};

/* -------- API types (Users Config backend) -------- */

export type AppUser = {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
};

export type CreateUserRequest = {
  email: string;
  displayName: string;
};