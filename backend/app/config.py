from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ASILI HAWK"
    version: str = "1.3.0-hybrid"
    debug: bool = True

    # Free public endpoints (no key required for basic discovery)
    pumpfun_base: str = "https://frontend-api-v3.pump.fun"
    dexscreener_base: str = "https://api.dexscreener.com"

    # Optional paid APIs (set in .env when available)
    birdeye_api_key: str = ""
    helius_api_key: str = ""
    solana_tracker_key: str = ""

    # Hybrid discovery windows
    # Ultra-new is included but scored harshly; emerging/graduating/post-grad preferred.
    max_age_minutes: int = 360          # hybrid: up to ~6h
    min_curve_progress: float = 3.0
    max_curve_progress: float = 99.5    # allow near-graduation
    min_usd_mcap: float = 400.0
    max_usd_mcap: float = 350_000.0     # allow early post-grad range
    min_reply_count: int = 0

    # Soft preference bands (minutes) — used by ranking hints
    hybrid_emerging_min: int = 6
    hybrid_emerging_max: int = 45
    hybrid_postgrad_max: int = 180

    # Cache
    cache_ttl_seconds: int = 25

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
