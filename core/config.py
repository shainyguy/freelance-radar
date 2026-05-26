"""
Конфигурация проекта — все настройки из .env файла.
"""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram ───────────────────────────────────
    BOT_TOKEN: str = ""
    ADMIN_IDS: str = ""

    # ── Database ───────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./freelance_radar.db"

    # ── GigaChat (Client ID + Auth Key) ────────────
    GIGACHAT_CLIENT_ID: str = ""
    GIGACHAT_AUTH_KEY: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"

    # ── YooKassa ───────────────────────────────────
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""

    # ── Proxy ──────────────────────────────────────
    PROXIES: str = ""

    # ── Parsing ────────────────────────────────────
    PARSE_INTERVAL_SECONDS: int = 120

    # ── Misc ───────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    PORT: int = 8080

    def get_admin_ids(self) -> list[int]:
        if not self.ADMIN_IDS or not self.ADMIN_IDS.strip():
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    def get_proxies(self) -> list[str]:
        if not self.PROXIES or not self.PROXIES.strip():
            return []
        return [x.strip() for x in self.PROXIES.split(",") if x.strip()]

    def is_admin(self, tg_id: int) -> bool:
        return tg_id in self.get_admin_ids()

    def get_tier_limits(self, tier: str) -> dict:
        return _TIER_LIMITS.get(tier, _TIER_LIMITS["free"])


_TIER_LIMITS = {
    "free": {
        "exchanges_limit": 2, "notifications_per_day": 10, "delay_seconds": 300,
        "ai_credits_per_month": 3, "ai_scoring": False, "ai_scam_detector": False,
        "ai_negotiator": False, "filter_profiles": 1,
    },
    "pro": {
        "exchanges_limit": 999, "notifications_per_day": 999999, "delay_seconds": 0,
        "ai_credits_per_month": 100, "ai_scoring": True, "ai_scam_detector": True,
        "ai_negotiator": False, "filter_profiles": 5,
    },
    "business": {
        "exchanges_limit": 999, "notifications_per_day": 999999, "delay_seconds": 0,
        "ai_credits_per_month": 1000, "ai_scoring": True, "ai_scam_detector": True,
        "ai_negotiator": True, "filter_profiles": 999,
    },
}

PRICING = {
    "pro":      {"1": 490,  "3": 1250,  "12": 3822},
    "business": {"1": 1490, "3": 3800,  "12": 11622},
}

settings = Settings()
