from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ASILI HAWK"
    version: str = "2.4.0-aie-merge"
    # Was True by default — fine for local dev, wrong default for a
    # deployed API (verbose errors/stack traces exposed to callers).
    debug: bool = False

    pumpfun_base: str = "https://frontend-api-v3.pump.fun"
    dexscreener_base: str = "https://api.dexscreener.com"

    birdeye_api_key: str = ""
    helius_api_key: str = ""
    solana_tracker_key: str = ""

    # Birth-channel window
    max_age_minutes: int = 360
    min_curve_progress: float = 3.0
    max_curve_progress: float = 99.5
    min_usd_mcap: float = 400.0
    max_usd_mcap: float = 500_000.0

    # Active-trade channel (runners Jupiter-like)
    active_max_age_minutes: int = 1440   # 24h
    active_max_usd_mcap: float = 3_000_000.0

    hybrid_emerging_min: int = 6
    hybrid_emerging_max: int = 45
    hybrid_postgrad_max: int = 180

    min_reply_count: int = 0
    cache_ttl_seconds: int = 25

    # Where the sqlite snapshot store lives. Override with DB_PATH in
    # deploy envs whose writable path differs (e.g. a mounted volume).
    db_path: str = "data/hawk_snapshots.db"

    # CORS: comma-separated origins. Defaults to permissive for local/dev use;
    # set CORS_ORIGINS in production to lock this down.
    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
