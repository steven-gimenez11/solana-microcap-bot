from dataclasses import dataclass
import os

def _float(name, default):
    try: return float(os.getenv(name, default))
    except (TypeError, ValueError): return default
def _int(name, default):
    try: return int(os.getenv(name, default))
    except (TypeError, ValueError): return default
def _bool(name, default): return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    min_market_cap_usd: float = _float("MIN_MARKET_CAP_USD", 50000)
    max_market_cap_usd: float = _float("MAX_MARKET_CAP_USD", 3000000)
    min_liquidity_usd: float = _float("MIN_LIQUIDITY_USD", 25000)
    min_volume_24h_usd: float = _float("MIN_VOLUME_24H_USD", 50000)
    max_pair_age_hours: float = _float("MAX_PAIR_AGE_HOURS", 72)
    min_score: float = _float("MIN_SCORE", 80)
    scan_interval: int = _int("SCAN_INTERVAL", 60)
    database_path: str = os.getenv("DATABASE_PATH", "data/scanner.db")
    dry_run: bool = _bool("DRY_RUN", True)
    trading_enabled: bool = _bool("TRADING_ENABLED", False)
    api_url: str = os.getenv("DEXSCREENER_API_URL", "https://api.dexscreener.com")
    request_timeout: float = _float("REQUEST_TIMEOUT_SECONDS", 10)
settings = Settings()
if settings.trading_enabled or not settings.dry_run:
    raise RuntimeError("This version is DRY-RUN only: keep DRY_RUN=true and TRADING_ENABLED=false")