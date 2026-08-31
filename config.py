from typing import List

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: SecretStr
    DATABASE_URL: str
    ADMIN_ID: List[int]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Settings()

