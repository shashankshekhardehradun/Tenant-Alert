from tenant_alert.config import Settings


def test_default_settings() -> None:
    settings = Settings()
    assert settings.app_name == "tenant-alert"
    assert settings.bq_dataset_gold == "gold"
