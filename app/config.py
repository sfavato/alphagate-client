from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    BITGET_API_KEY: str
    BITGET_SECRET_KEY: str
    BITGET_PASSPHRASE: str
    ALPHAGATE_HMAC_SECRET: str
    DRY_RUN: bool = False

    # --- Nouveaux Paramètres Utilisateur ---
    # Levier par défaut (ex: 10 pour 10x)
    DEFAULT_LEVERAGE: int = 5

    # Pourcentage du solde disponible à utiliser par trade (ex: 0.05 pour 5%)
    TRADE_ALLOCATION_PERCENT: float = 0.05

    # --- Mission 1 : Notifications ---
    # L'utilisateur mettra son URL Webhook Discord ici
    DISCORD_WEBHOOK_URL: Optional[str] = None
    # Optionnel : Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # --- Mission 3 : Filtrage ---
    # Liste noire d'actifs (ex: ["DOGE/USDT", "PEPE/USDT"])
    SYMBOL_BLACKLIST: List[str] = []
    # Liste blanche (si non vide, SEULS ces symboles sont tradés)
    SYMBOL_WHITELIST: List[str] = []

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings():
    return Settings()
