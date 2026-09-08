"""
Configuration for fidelityAPI — the mobile-facing service.

Crucially, this service has NO setting for pos.db's path at all. It cannot
open Aronium's database even by mistake; the only way it ever learns
anything about customers, sales, or products is by calling generalAPI over
HTTP with its own server-to-server secret.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OUR OWN database, where points/loyalty data lives. Aronium never
    # touches or knows about this file.
    loyalty_db_path: str = "./loyalty.db"

    # Secret the MOBILE APP must send. Grants zero access to pos.db.
    fidelity_api_key: str = "change-me-to-a-long-random-secret-2"

    # Where generalAPI lives, and the server-to-server secret used to call
    # it. The mobile app never sees general_api_key.
    general_api_base_url: str = "http://127.0.0.1:8001"
    general_api_key: str = "change-me-to-a-long-random-secret-1"

    # Points earned per 1 currency unit spent.
    points_per_currency_unit: float = 1.0

    # Currency value of a point for cash-style redemption / display.
    point_redemption_value: float = 0.05

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
