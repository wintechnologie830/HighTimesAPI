"""
Central configuration for the API.

All values can be overridden with environment variables or a `.env` file
(copy `.env.example` to `.env` and edit it).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Path to Aronium's own database. We only ever open this READ-ONLY.
    aronium_db_path: str = r"C:\Users\alikh\AppData\Local\Aronium\Data\pos.db"

    # Path to OUR OWN database, where points/loyalty data lives.
    # This is a completely separate file from pos.db.
    loyalty_db_path: str = "./loyalty.db"

    # Points earned per 1 currency unit spent (e.g. 1 => 1 point per $1)
    points_per_currency_unit: float = 1.0

    # Currency value of a single point when redeemed (e.g. 0.05 => 1 point = $0.05)
    point_redemption_value: float = 0.05

    # Simple shared-secret API key required in the "X-API-Key" header
    api_key: str = "change-me-to-a-long-random-secret"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
