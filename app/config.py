from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    BITGET_API_KEY: str
    BITGET_SECRET_KEY: str
    BITGET_PASSPHRASE: str
    ALPHAGATE_HMAC_SECRET: str
    DRY_RUN: bool = False

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings():
    return Settings()
