from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    aronium_db_path: str = r"C:\Users\alikh\AppData\Local\Aronium\Data\pos.db"

    general_api_key: str = "change-me-to-a-long-random-secret-1"

    host: str = "127.0.0.1"
    port: int = 8001

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
