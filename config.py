from dataclasses import dataclass
import os


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name, default):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    min_market_cap_usd: float = _float("MIN_MARKET_CAP_USD", 50000)
    max_market_cap_usd: float = _float("MAX_MARKET_CAP_USD", 1500000)
    min_liquidity_usd: float = _float("MIN_LIQUIDITY_USD", 25000)
    min_volume_24h_usd: float = _float("MIN_VOLUME_24H_USD", 50000)
    max_pair_age_hours: float = _float("MAX_PAIR_AGE_HOURS", 72)
    min_score: float = _float("MIN_SCORE", 80)
    max_candidate_risk: float = _float("MAX_CANDIDATE_RISK", 25)
    scan_interval: int = _int("SCAN_INTERVAL", 60)
    database_path: str = os.getenv("DATABASE_PATH", "data/scanner.db")
    dry_run: bool = _bool("DRY_RUN", True)
    trading_enabled: bool = _bool("TRADING_ENABLED", False)
    live_trading_ack: str = os.getenv("LIVE_TRADING_ACK", "")
    api_url: str = os.getenv("DEXSCREENER_API_URL", "https://api.dexscreener.com")
    solana_rpc_url: str = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    request_timeout: float = _float("REQUEST_TIMEOUT_SECONDS", 12)

    paper_initial_capital_usd: float = _float("PAPER_INITIAL_CAPITAL_USD", 10)
    max_total_capital_usd: float = _float("MAX_TOTAL_CAPITAL_USD", 10)
    max_position_usd: float = _float("MAX_POSITION_USD", 1)
    max_open_positions: int = _int("MAX_OPEN_POSITIONS", 3)

    capital_recovery_multiple: float = _float("CAPITAL_RECOVERY_MULTIPLE", 2)
    take_profit_1_multiple: float = _float("TAKE_PROFIT_1_MULTIPLE", _float("TAKE_PROFIT_1", 5))
    take_profit_2_multiple: float = _float("TAKE_PROFIT_2_MULTIPLE", _float("TAKE_PROFIT_2", 10))
    moonbag_enabled: bool = _bool("MOONBAG_ENABLED", True)

    jupiter_api_url: str = os.getenv("JUPITER_API_URL", "https://api.jup.ag")
    jupiter_api_key: str = os.getenv("JUPITER_API_KEY", "")
    solana_private_key_b58: str = os.getenv("SOLANA_PRIVATE_KEY_B58", "")
    max_price_impact_pct: float = _float("MAX_PRICE_IMPACT_PCT", 5.0)
    min_sol_reserve: float = _float("MIN_SOL_RESERVE", 0.003)
    live_entry_cooldown_hours: float = _float("LIVE_ENTRY_COOLDOWN_HOURS", 24)
    live_min_asymmetry_score: float = _float("LIVE_MIN_ASYMMETRY_SCORE", 70)
    live_min_momentum_score: float = _float("LIVE_MIN_MOMENTUM_SCORE", 55)

    @property
    def live_mode(self):
        return (
            self.trading_enabled
            and not self.dry_run
            and self.live_trading_ack == "I_ACCEPT_REAL_LOSS_RISK"
        )


settings = Settings()

# Fail closed: accidental env changes can never enable trading without the explicit acknowledgement.
if settings.trading_enabled and not settings.live_mode:
    raise RuntimeError(
        "TRADING_ENABLED=true requires DRY_RUN=false and "
        "LIVE_TRADING_ACK=I_ACCEPT_REAL_LOSS_RISK"
    )
