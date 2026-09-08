"""
Configuration for generalAPI — the ONLY service in this project allowed to
open Aronium's pos.db. Every value here can be overridden via .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Path to Aronium's own database. Opened READ-ONLY, always.
    aronium_db_path: str = r"C:\Users\alikh\AppData\Local\Aronium\Data\pos.db"

    # Shared secret that ONLY fidelityAPI is configured with. The mobile
    # app never sees this key and never talks to this service directly.
    general_api_key: str = "change-me-to-a-long-random-secret-1"

    # Bind address for uvicorn. Keep this as 127.0.0.1 in production so this
    # service is unreachable from the store's Wi-Fi network - only
    # fidelityAPI (running on the same machine) can reach it.
    host: str = "127.0.0.1"
    port: int = 8001

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
