from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_app_settings
from app.main import create_app


def test_system_status_exposes_safe_provider_configuration():
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        environment="test",
        memory_provider="cognee_cloud",
        atlas_provider="cognee_cloud",
        atlas_dataset_name="mizaaj_atlas_seed_v2",
        cognee_cloud_base_url="https://tenant.aws.cognee.ai",
        cognee_cloud_api_key="secret-key",
    )
    client = TestClient(app)

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "test"
    assert payload["memory_provider"] == "cognee_cloud"
    assert payload["atlas_provider"] == "cognee_cloud"
    assert payload["atlas_dataset_name"] == "mizaaj_atlas_seed_v2"
    assert payload["cognee_cloud_configured"] is True
    assert payload["cloud_usage"]["token_price_usd_per_million"] == 2.5
    assert "secret-key" not in response.text
