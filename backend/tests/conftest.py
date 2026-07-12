import pytest

from app.core.config import get_settings
from app.core.dependencies import get_reasoning_gateway


@pytest.fixture(autouse=True)
def use_local_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    get_reasoning_gateway.cache_clear()
    yield
    get_reasoning_gateway.cache_clear()
    get_settings.cache_clear()
