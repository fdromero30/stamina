from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    users_config_api_url: str = "http://localhost:8080"

    # ── Trading Cycle ─────────────────────────────────────────────────
    trading_interval_seconds: int = 300  # 5 minutes default
    default_leverage: int = 1
    risk_per_trade: float = 0.005  # 0.5% of available account per trade
    max_open_positions: int = 2
    break_even_ratio: float = 1.5  # Move SL to breakeven at 1.5:1

    # ── Trading Hours (EUR/USD: Sun 5pm ET → Fri 5pm ET) ──────────────
    # Use 24h format in US/Eastern timezone
    trading_window_start: str = "17:00"   # Sunday 5pm ET
    trading_window_end: str = "17:00"     # Friday 5pm ET
    trading_timezone: str = "US/Eastern"

    # ── Strategy Defaults ─────────────────────────────────────────────
    default_ma_short: int = 9
    default_ma_long: int = 200
    default_candle_interval: str = "5m"
    default_candle_count: int = 300

    # ── Swing Lookback (for SL calculation) ───────────────────────────
    swing_lookback_candles: int = 20

    # ── Fallback Balance ──────────────────────────────────────────────
    fallback_account_balance: float = 10000.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()