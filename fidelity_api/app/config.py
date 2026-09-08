from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    loyalty_db_path: str = "./loyalty.db"

    fidelity_api_key: str = "change-me-to-a-long-random-secret-2"

    # A second, separate secret gating the staff pickup screen (looking up
    # redemption codes, marking them fulfilled). Deliberately not the same
    # as fidelity_api_key: every customer's browser already has that key
    # configured just to use the app at all, so it can't double as "this
    # is staff."
    staff_pin: str = "change-me-staff-pin"

    general_api_base_url: str = "http://127.0.0.1:8001"
    general_api_key: str = "change-me-to-a-long-random-secret-1"

    points_per_currency_unit: float = 1.0

    point_redemption_value: float = 0.05

    # How often (seconds) the background loop checks Aronium for new sales
    # documents and awards points for the ones tied to a real customer -
    # this is what makes a sale rung up directly at the Aronium till earn
    # points automatically, not just ones made through the loyalty app.
    auto_sync_interval_seconds: int = 30

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
