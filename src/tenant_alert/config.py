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
    soda_app_token: str = ""
    gcs_raw_bucket: str = ""
    local_data_dir: str = "data"
    etl_upload_to_gcs: bool = False
    etl_load_to_bigquery: bool = False

    @property
    def raw_bucket_name(self) -> str:
        """Return the configured raw-data bucket or the Terraform default name."""
        if self.gcs_raw_bucket:
            return self.gcs_raw_bucket
        if not self.gcp_project_id:
            return ""
        return f"{self.gcp_project_id}-{self.environment}-raw"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
