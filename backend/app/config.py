from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ASILI HAWK"
    version: str = "0.3.0"
    debug: bool = True

    # Free public endpoints (no key required for basic discovery)
    pumpfun_base: str = "https://frontend-api-v3.pump.fun"
    dexscreener_base: str = "https://api.dexscreener.com"

    # Optional paid APIs (set in .env when available)
    birdeye_api_key: str = ""
    helius_api_key: str = ""
    solana_tracker_key: str = ""

    # Discovery tuning
    max_age_minutes: int = 180          # only care about very fresh launches
    min_curve_progress: float = 5.0     # ignore dead / dust starts
    max_curve_progress: float = 95.0    # still on curve = the edge
    min_usd_mcap: float = 400.0
    max_usd_mcap: float = 150_000.0     # pre / near graduation
    min_reply_count: int = 0

    # Cache
    cache_ttl_seconds: int = 25

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
