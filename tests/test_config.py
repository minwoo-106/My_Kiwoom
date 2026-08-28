import pytest

from app.config import ConfigurationError, MOCK_API_HOST, Settings, assert_mock_host


def test_mock_configuration_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("KIWOOM_ENV", "mock")
    monkeypatch.setenv("KIWOOM_APP_KEY", "test-app-key")
    monkeypatch.setenv("KIWOOM_SECRET_KEY", "test-secret")

    settings = Settings.load(tmp_path / "missing.env")

    assert settings.api_host == MOCK_API_HOST


@pytest.mark.parametrize("environment", ["real", "production", "MOCK "])
def test_non_mock_environment_is_rejected(monkeypatch, tmp_path, environment):
    monkeypatch.setenv("KIWOOM_ENV", environment)
    monkeypatch.setenv("KIWOOM_APP_KEY", "key")
    monkeypatch.setenv("KIWOOM_SECRET_KEY", "secret")

    with pytest.raises(ConfigurationError):
        Settings.load(tmp_path / "missing.env")


def test_production_host_is_blocked():
    with pytest.raises(ConfigurationError):
        assert_mock_host("https://api.kiwoom.com")


def test_host_override_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("KIWOOM_ENV", "mock")
    monkeypatch.setenv("KIWOOM_APP_KEY", "key")
    monkeypatch.setenv("KIWOOM_SECRET_KEY", "secret")
    monkeypatch.setenv("KIWOOM_API_HOST", "https://api.kiwoom.com")

    with pytest.raises(ConfigurationError, match="blocked permanently"):
        Settings.load(tmp_path / "missing.env")

