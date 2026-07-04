import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def use_local_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
