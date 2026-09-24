from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Veta"
    app_env: str = "lab"
    secret_key: str = "veta-lab-secret-change-in-this-machine-only"
    access_token_expire_minutes: int = 720
    algorithm: str = "HS256"

    database_url: str = "postgresql+asyncpg://veta:veta@localhost:5432/veta"
    mongodb_url: str = "mongodb://localhost:27017"
    mongo_db: str = "veta_telemetry"

    api_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    seed_on_start: bool = False
    media_dir: str = "media"
    content_model_mode: Literal["heuristic", "shadow", "mmoe"] = "heuristic"
    ads_model_mode: Literal["heuristic", "shadow", "mmoe"] = "heuristic"
    mmoe_model_path: str = "artifacts/mmoe/model.json"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.api_cors_origins.split(",") if item.strip()]


settings = Settings()
