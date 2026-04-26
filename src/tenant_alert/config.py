"""Application configuration primitives used across services."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration loaded from env vars and .env files."""

    app_name: str = "tenant-alert"
    environment: str = "dev"
    gcp_project_id: str = ""
    bq_location: str = "US"
    bq_dataset_bronze: str = "bronze"
    bq_dataset_silver: str = "silver"
    bq_dataset_gold: str = "gold"
    bq_dataset_ml: str = "ml"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
