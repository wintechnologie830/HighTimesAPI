from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    loyalty_db_path: str = "./loyalty.db"

    fidelity_api_key: str = "change-me-to-a-long-random-secret-2"

    general_api_base_url: str = "http://127.0.0.1:8001"
    general_api_key: str = "change-me-to-a-long-random-secret-1"

    points_per_currency_unit: float = 1.0

    point_redemption_value: float = 0.05

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
