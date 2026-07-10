export type AuthMode = "login" | "signup";

export type Session = {
  id: string;
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
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

/* -------- API Key types -------- */

export type ApiKeyRow = {
  id: string;
  label: string;
  broker: string;
  maskedKey: string;
  createdAt: string;
};

export type CreateApiKeyRequest = {
  userId: string;
  label: string;
  broker: string;
  publicKey: string;
  privateKey: string;
};

export type RevealedKeyResponse = {
  apiKey: string;
};
