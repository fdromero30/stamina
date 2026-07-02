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
