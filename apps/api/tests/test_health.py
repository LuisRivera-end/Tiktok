from app.config import settings


def test_lab_settings_are_local():
    assert settings.app_name
    assert "localhost" in settings.database_url or "postgres" in settings.database_url
