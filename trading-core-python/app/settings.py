from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    users_config_api_url: str = "http://localhost:8080"
    database_url: str = ""

    # ── Trading Cycle ─────────────────────────────────────────────────
    trading_interval_seconds: int = 300  # 5 minutes default
    default_leverage: int = 5  # 5x leverage (fixed for all operations)
    # Execute trades against the eToro DEMO account (the whole stack runs
    # in demo mode; real execution routes return 404 RouteNotFound for
    # demo keys).
    use_demo_account: bool = True
    risk_per_trade: float = 0.005  # 0.5% of available account per trade
    max_open_positions: int = 2
    break_even_ratio: float = 1.5  # Legacy: retained for backward compatibility

    # ── Stop Loss — ATR-based (regla: SL = MA200 ∓ ATR × multiplier) ──
    # El ATR(14) mide cuánto se mueve el activo en promedio por vela.
    # Para dar "aire" al SL y que no sea rechazado por eToro:
    #   BUY  → SL = MA200 − ATR14 × sl_atr_multiplier
    #   SELL → SL = MA200 + ATR14 × sl_atr_multiplier
    sl_atr_multiplier: float = 1.5
    # Distancia mínima entre el entry y el SL (en pips) para evitar
    # rechazo del broker (eToro exige un mínimo).
    sl_min_distance_pips: float = 10.0

    # ── Transversal Risk Management (máquina de estados + trailing ATR) ─
    # Defaults — overridable per strategy via the Java backend.
    hito1_trigger_r: float = 1.0      # SL → breakeven + spread
    hito2_trigger_r: float = 1.5      # SL → +1.0R and activate trailing
    hito2_sl_r: float = 1.0           # Minimum secured R in Hito 2
    breakeven_spread_mult: float = 1.0
    trailing_enabled: bool = True
    trailing_atr_mult: float = 1.2
    trailing_atr_period: int = 14
    max_tp_far_r: float = 5.0         # Far TP to "deactivate" the fixed TP
    use_candle_high_low: bool = True
    sl_update_retry_seconds: int = 5
    min_sl_update_spacing_pips: float = 1.0

    # ── Trading Hours (EUR/USD: Sun 5pm ET → Fri 5pm ET) ──────────────
    # Use 24h format in US/Eastern timezone
    trading_window_start: str = "17:00"   # Sunday 5pm ET
    trading_window_end: str = "17:00"     # Friday 5pm ET
    trading_timezone: str = "US/Eastern"

    # ── News Blackout (alto riesgo) ────────────────────────────────────
    # El bot se detiene 30 min antes y 30 min después de eventos High de
    # EUR/USD publicados en el calendario económico semanal.
    news_calendar_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    news_blackout_before_minutes: int = 30
    news_blackout_after_minutes: int = 30
    news_prefetch_minutes: int = 5                 # 5 min antes del blackout → refresh del feed
    news_relevant_countries: str = "EUR,USD"
    news_impact_levels: str = "High"
    news_refresh_after_idle_minutes: int = 60      # tras un long sleep → refresh
    news_reopen_max_spread_pips: float = 3.0       # EUR/USD: 3 pips = 0.0003
    news_reopen_spread_check_minutes: int = 5
    news_blackout_protect_positions: bool = True
    news_fetch_fail_mode: str = "fail_open"        # "fail_open" | "fail_closed"

    # ── Strategy Defaults ─────────────────────────────────────────────
    default_ma_short: int = 9
    default_ma_long: int = 200
    default_candle_interval: str = "5m"
    default_candle_count: int = 300

    # ── Swing Lookback (for SL calculation) ───────────────────────────
    swing_lookback_candles: int = 20

    # ── Crossover Window: ONLY the most recent completed candle is scanned.
    #    (1 = confirm the cross on the closed candle and enter at its close;
    #     does not chase signals from older candles)
    crossover_window_candles: int = 1

    # ── Risk : Reward for Take Profit (TP = risk * ratio) ─────────────
    risk_reward_ratio: float = 2.0

    # ── Expansion Filter (ATR): discard entries whose confirmation candle
    #    moved more than max_candle_expansion_atr_mult × ATR(atr_period)
    #    (protects against entering far from the optimal level after a
    #     news/expansion candle) ─────────────────────────────────────────
    atr_period: int = 14
    max_candle_expansion_atr_mult: float = 1.8

    # ── Fallback Balance ──────────────────────────────────────────────
    fallback_account_balance: float = 10000.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()