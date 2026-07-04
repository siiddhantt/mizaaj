import json
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError, ProviderRequestError
from app.domain.captures.schemas import CaptureCreate, UploadedAsset
from app.domain.common import CaptureSourceType, ClothingCategory
from app.domain.extraction.openrouter import OpenRouterExtractionGateway


def openrouter_settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_text_model="deepseek-test",
        openrouter_vision_model="qwen-vision-test",
        openrouter_site_url="https://mizaaj.test",
        openrouter_app_title="Mizaaj Test",
    )


def response_payload() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "brand": "Uniqlo",
                            "retailer": "Uniqlo",
                            "title": "Linen Blend Relaxed Shirt",
                            "sku": "SKU-123",
                            "url": "https://shop.test/products/sku-123",
                            "category": "shirt",
                            "color": "navy",
                            "material": "linen, cotton",
                            "size_options": ["M", "L", "M"],
                            "size_labels": [
                                {
                                    "label": "L",
                                    "system": "UK",
                                    "region": "UK",
                                    "audience": "men",
                                },
                                {
                                    "label": "L",
                                    "system": "EUR",
                                    "region": "EU",
                                    "audience": "men",
                                },
                            ],
                            "size_chart": [
                                {
                                    "size": "M",
                                    "measurements": [{"name": "chest", "value": 104, "unit": "cm"}],
                                }
                            ],
                            "fit_descriptors": ["relaxed fit"],
                            "fabric_composition": [
                                {"material": "linen", "percentage": 55, "component": "shell"},
                                {"material": "cotton", "percentage": 45, "component": "shell"},
                            ],
                            "care_instructions": [
                                {"instruction": "machine wash cold", "category": "washing"}
                            ],
                            "origin_country": "India",
                            "gender": "men",
                            "product_identifiers": [{"kind": "sku", "value": "SKU-123"}],
                            "attributes": [{"name": "closure", "value": "button front"}],
                            "claims": [
                                {
                                    "predicate": "silhouette",
                                    "value": "relaxed fit",
                                    "source": "product page",
                                    "confidence": 0.82,
                                }
                            ],
                        }
                    )
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_text_capture_uses_text_model_and_structured_output():
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.headers["http-referer"] == "https://mizaaj.test"
        assert request.headers["x-openrouter-title"] == "Mizaaj Test"
        return httpx.Response(200, json=response_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        draft = await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.manual,
                page_url="https://shop.test/products/sku-123",
                text_blocks=["Uniqlo linen shirt. Sizes M L."],
            )
        )

    request_payload = requests[0]
    assert request_payload["model"] == "deepseek-test"
    assert request_payload["require_parameters"] is True
    assert request_payload["response_format"]["json_schema"]["strict"] is True
    assert isinstance(request_payload["messages"][1]["content"], str)
    assert draft.brand == "Uniqlo"
    assert draft.category == ClothingCategory.shirt
    assert draft.size_options == ["M", "L", "UK L", "EUR L"]
    assert [label.system for label in draft.size_labels] == ["UK", "EUR"]
    assert draft.fabric_composition[0].material == "linen"
    assert draft.extracted_claims[0].predicate == "silhouette"


@pytest.mark.asyncio
async def test_image_capture_uses_vision_model_and_image_parts():
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert str(request.url) == "https://cdn.test/size-chart.png"
            return httpx.Response(
                200,
                content=b"image-bytes",
                headers={"content-type": "image/png"},
            )

        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.upload,
                assets=[
                    UploadedAsset(
                        path="users/local/size-chart.png",
                        public_url="https://cdn.test/size-chart.png",
                        original_name="size-chart.png",
                    )
                ],
            )
        )

    request_payload = requests[0]
    content = request_payload["messages"][1]["content"]
    assert request_payload["model"] == "qwen-vision-test"
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_non_image_upload_uses_text_model_and_text_evidence():
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.upload,
                text_blocks=["The Bear House tag says UK L and EUR L."],
                assets=[
                    UploadedAsset(
                        path="users/local/tag.txt",
                        public_url="https://cdn.test/tag.txt",
                        original_name="tag.txt",
                        mime_type="text/plain",
                    )
                ],
            )
        )

    request_payload = requests[0]
    assert request_payload["model"] == "deepseek-test"
    assert isinstance(request_payload["messages"][1]["content"], str)
    assert "UK L and EUR L" in request_payload["messages"][1]["content"]


@pytest.mark.asyncio
async def test_image_capture_reports_unreadable_upload():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        with pytest.raises(ProviderRequestError, match="Uploaded image could not be read"):
            await gateway.extract_product(
                CaptureCreate(
                    user_id=uuid4(),
                    source_type=CaptureSourceType.upload,
                    assets=[
                        UploadedAsset(
                            path="users/local/size-chart.png",
                            public_url="https://cdn.test/size-chart.png",
                            original_name="size-chart.png",
                        )
                    ],
                )
            )


@pytest.mark.asyncio
async def test_evidence_overrides_incorrect_model_category():
    payload = response_payload()
    content = json.loads(payload["choices"][0]["message"]["content"])
    content["title"] = "AIRism Cotton Oversized T-Shirt"
    content["category"] = "trousers"
    payload["choices"][0]["message"]["content"] = json.dumps(content)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        draft = await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.manual,
                text_blocks=["UNIQLO AIRism Cotton Oversized T-Shirt. Sizes S M L XL."],
            )
        )

    assert draft.category == ClothingCategory.tshirt


@pytest.mark.asyncio
async def test_extraction_normalizes_regional_size_labels_and_drops_placeholder_ids():
    payload = response_payload()
    content = json.loads(payload["choices"][0]["message"]["content"])
    content["size_options"] = ["UK L", "EUR L"]
    content["size_labels"] = [
        {"label": "UK L", "system": "letter", "region": None, "audience": "men"},
        {"label": "EUR L", "system": "letter", "region": None, "audience": "men"},
        {"label": "UK L", "system": "UK", "region": None, "audience": "men"},
    ]
    content["product_identifiers"] = [
        {"kind": "sku", "value": "N/A"},
        {"kind": "style", "value": "not visible"},
    ]
    payload["choices"][0]["message"]["content"] = json.dumps(content)

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        draft = await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.manual,
                text_blocks=["The Bear House tag says UK L and EUR L."],
            )
        )

    assert [(label.system, label.label) for label in draft.size_labels] == [
        ("UK", "L"),
        ("EUR", "L"),
    ]
    assert draft.size_options == ["UK L", "EUR L"]
    assert draft.product_identifiers == []
    assert all(claim.predicate != "product_identifiers" for claim in draft.extracted_claims)
    regional_claim = next(
        claim for claim in draft.extracted_claims if claim.predicate == "regional_size_labels"
    )
    assert regional_claim.value == "UK L, EUR L"


@pytest.mark.asyncio
async def test_extraction_recovers_fenced_json_payloads():
    payload = response_payload()
    content = payload["choices"][0]["message"]["content"]
    payload["choices"][0]["message"]["content"] = f"```json\n{content}\n```"

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        draft = await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.manual,
                text_blocks=["Uniqlo linen shirt. Sizes M L."],
            )
        )

    assert draft.brand == "Uniqlo"


@pytest.mark.asyncio
async def test_extraction_coerces_product_draft_wrapper_payloads():
    payload = response_payload()
    payload["choices"][0]["message"]["content"] = json.dumps(
        {
            "product_draft": {
                "title": "The Bear House black cotton drop shoulder t-shirt",
                "size_labels": ["UK L", "EUR L"],
                "size_options": ["UK L", "EUR L"],
                "fabric_composition": None,
                "care_instructions": None,
                "origin": None,
                "fit": "Relaxed silhouette",
                "style": "drop shoulder t-shirt",
                "sku": None,
                "article": None,
                "barcode": None,
                "evidence": [{"field": "size_labels", "value": ["UK L", "EUR L"], "source": "tag"}],
            }
        }
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        gateway = OpenRouterExtractionGateway(openrouter_settings(), client)
        draft = await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.manual,
                text_blocks=["The Bear House tag says UK L and EUR L."],
            )
        )

    assert draft.brand == "The Bear House"
    assert draft.title == "black cotton drop shoulder t-shirt"
    assert [(label.system, label.label) for label in draft.size_labels] == [
        ("UK", "L"),
        ("EUR", "L"),
    ]
    assert "Relaxed silhouette" in draft.fit_descriptors
    assert draft.product_identifiers == []


@pytest.mark.asyncio
async def test_openrouter_requires_api_key():
    settings = openrouter_settings().model_copy(update={"openrouter_api_key": None})
    gateway = OpenRouterExtractionGateway(settings)

    with pytest.raises(ProviderNotConfiguredError):
        await gateway.extract_product(
            CaptureCreate(
                user_id=uuid4(),
                source_type=CaptureSourceType.manual,
                text_blocks=["Cotton shirt"],
            )
        )
