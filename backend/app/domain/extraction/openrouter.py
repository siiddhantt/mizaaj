import base64
import json
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError, ProviderRequestError
from app.domain.captures.schemas import CaptureCreate, UploadedAsset
from app.domain.claims import ExtractedClaim
from app.domain.common import ClothingCategory
from app.domain.extraction.gateway import ExtractionGateway
from app.domain.products.schemas import (
    CareInstruction,
    Measurement,
    ProductAttribute,
    ProductDraft,
    ProductIdentifier,
    SizeLabel,
    SizeMeasurementSet,
    TextileComposition,
)

SYSTEM_PROMPT = """
You extract clothing product facts from messy shopping evidence.
Only use facts visible in the supplied text or images.
Return null or empty arrays when evidence is missing.
Do not infer personal fit outcomes, user preferences, or purchase decisions.
Preserve region-specific size labels exactly as shown, such as UK L and EUR L.
Do not convert clothing sizes between regions unless the evidence explicitly shows the mapping.
Use general garment knowledge only to choose field names and categories.
Do not invent product facts.
Write compact, evidence-grounded claim values a user can review before saving.
""".strip()

PRODUCT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "brand",
        "retailer",
        "title",
        "sku",
        "url",
        "category",
        "color",
        "material",
        "size_options",
        "size_labels",
        "size_chart",
        "fit_descriptors",
        "fabric_composition",
        "care_instructions",
        "origin_country",
        "gender",
        "product_identifiers",
        "attributes",
        "claims",
    ],
    "properties": {
        "brand": {"type": ["string", "null"]},
        "retailer": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "sku": {"type": ["string", "null"]},
        "url": {"type": ["string", "null"]},
        "category": {
            "type": "string",
            "enum": [category.value for category in ClothingCategory],
        },
        "color": {"type": ["string", "null"]},
        "material": {"type": ["string", "null"]},
        "size_options": {
            "type": "array",
            "description": (
                "Canonical display size options. Preserve regional labels as UK L "
                "or EUR L when visible."
            ),
            "items": {"type": "string"},
        },
        "size_labels": {
            "type": "array",
            "description": "Every region/system-specific size label visible on the tag or page.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "system", "region", "audience"],
                "properties": {
                    "label": {"type": "string"},
                    "system": {"type": ["string", "null"]},
                    "region": {"type": ["string", "null"]},
                    "audience": {"type": ["string", "null"]},
                },
            },
        },
        "size_chart": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["size", "measurements"],
                "properties": {
                    "size": {"type": "string"},
                    "measurements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "value", "unit"],
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "number"},
                                "unit": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "fit_descriptors": {
            "type": "array",
            "description": (
                "Visible fit or silhouette words such as relaxed, slim, regular, "
                "oversized, straight."
            ),
            "items": {"type": "string"},
        },
        "fabric_composition": {
            "type": "array",
            "description": (
                "Visible material composition entries, preserving percentages and "
                "garment components."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["material", "percentage", "component"],
                "properties": {
                    "material": {"type": "string"},
                    "percentage": {"type": ["number", "null"]},
                    "component": {"type": ["string", "null"]},
                },
            },
        },
        "care_instructions": {
            "type": "array",
            "description": "Visible care text or decoded care-symbol meaning.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["instruction", "category"],
                "properties": {
                    "instruction": {"type": "string"},
                    "category": {"type": ["string", "null"]},
                },
            },
        },
        "origin_country": {"type": ["string", "null"]},
        "gender": {"type": ["string", "null"]},
        "product_identifiers": {
            "type": "array",
            "description": "Visible SKU, style, article, barcode, EAN, or model identifiers.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "value"],
                "properties": {
                    "kind": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
        },
        "attributes": {
            "type": "array",
            "description": "Other visible clothing facts worth remembering.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "value"],
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["predicate", "value", "source", "confidence"],
                "properties": {
                    "predicate": {"type": "string"},
                    "value": {"type": "string"},
                    "source": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    },
}


class OpenRouterClaim(BaseModel):
    predicate: str
    value: str
    source: str | None = None
    confidence: float = Field(default=0.65, ge=0, le=1)

    model_config = ConfigDict(extra="ignore")


class OpenRouterMeasurement(BaseModel):
    name: str
    value: float
    unit: str = "cm"

    model_config = ConfigDict(extra="ignore")


class OpenRouterSizeSet(BaseModel):
    size: str
    measurements: list[OpenRouterMeasurement] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class OpenRouterSizeLabel(BaseModel):
    label: str
    system: str | None = None
    region: str | None = None
    audience: str | None = None

    model_config = ConfigDict(extra="ignore")


class OpenRouterTextileComposition(BaseModel):
    material: str
    percentage: float | None = None
    component: str | None = None

    model_config = ConfigDict(extra="ignore")


class OpenRouterCareInstruction(BaseModel):
    instruction: str
    category: str | None = None

    model_config = ConfigDict(extra="ignore")


class OpenRouterProductIdentifier(BaseModel):
    kind: str
    value: str

    model_config = ConfigDict(extra="ignore")


class OpenRouterProductAttribute(BaseModel):
    name: str
    value: str

    model_config = ConfigDict(extra="ignore")


class OpenRouterProductPayload(BaseModel):
    brand: str | None = None
    retailer: str | None = None
    title: str | None = None
    sku: str | None = None
    url: str | None = None
    category: str = ClothingCategory.unknown.value
    color: str | None = None
    material: str | None = None
    size_options: list[str] = Field(default_factory=list)
    size_labels: list[OpenRouterSizeLabel] = Field(default_factory=list)
    size_chart: list[OpenRouterSizeSet] = Field(default_factory=list)
    fit_descriptors: list[str] = Field(default_factory=list)
    fabric_composition: list[OpenRouterTextileComposition] = Field(default_factory=list)
    care_instructions: list[OpenRouterCareInstruction] = Field(default_factory=list)
    origin_country: str | None = None
    gender: str | None = None
    product_identifiers: list[OpenRouterProductIdentifier] = Field(default_factory=list)
    attributes: list[OpenRouterProductAttribute] = Field(default_factory=list)
    claims: list[OpenRouterClaim] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class OpenRouterExtractionGateway(ExtractionGateway):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def extract_product(self, capture: CaptureCreate) -> ProductDraft:
        if not self.settings.openrouter_api_key:
            raise ProviderNotConfiguredError(
                "OPENROUTER_API_KEY is required for OpenRouter extraction."
            )

        image_inputs = await self._image_inputs(capture)
        response = await self._request_completion(
            model=self._model_for(image_inputs),
            content=self._message_content(capture, image_inputs),
        )
        payload = self._parse_payload(response)
        return self._to_product_draft(payload, capture)

    def _model_for(self, image_inputs: list[str]) -> str:
        if image_inputs:
            return self.settings.openrouter_vision_model
        return self.settings.openrouter_text_model

    async def _image_inputs(self, capture: CaptureCreate) -> list[str]:
        assets = [
            asset for asset in capture.assets if asset.public_url and self._is_image_asset(asset)
        ]
        assets = assets[: self.settings.extraction_max_images]
        if not assets:
            return []

        client = self.client
        if client is not None:
            return [await self._image_data_url(client, asset) for asset in assets]

        async with httpx.AsyncClient(
            timeout=self.settings.openrouter_timeout_seconds
        ) as scoped_client:
            return [await self._image_data_url(scoped_client, asset) for asset in assets]

    def _is_image_asset(self, asset: UploadedAsset) -> bool:
        mime_type = (asset.mime_type or "").lower()
        if mime_type.startswith("image/"):
            return True

        name = (asset.original_name or asset.path).lower()
        return name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"))

    async def _image_data_url(self, client: httpx.AsyncClient, asset: UploadedAsset) -> str:
        if not asset.public_url:
            raise ProviderRequestError("Uploaded image is missing a readable URL.")

        try:
            response = await client.get(asset.public_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                "Uploaded image could not be read for extraction. Check the S3 endpoint URL."
            ) from exc

        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        if len(response.content) > max_bytes:
            raise ProviderRequestError(
                "Uploaded image is larger than "
                f"the {self.settings.max_upload_mb} MB extraction limit."
            )

        mime_type = response.headers.get("content-type") or asset.mime_type or "image/jpeg"
        if not mime_type.startswith("image/"):
            mime_type = asset.mime_type or "image/jpeg"

        encoded = base64.b64encode(response.content).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _message_content(
        self, capture: CaptureCreate, image_inputs: list[str]
    ) -> str | list[dict[str, Any]]:
        prompt = self._user_prompt(capture)
        if not image_inputs:
            return prompt

        return [
            {"type": "text", "text": prompt},
            *[{"type": "image_url", "image_url": {"url": url}} for url in image_inputs],
        ]

    def _user_prompt(self, capture: CaptureCreate) -> str:
        evidence = "\n\n".join(part for part in capture.text_blocks if part.strip())
        evidence = evidence[: self.settings.extraction_max_text_chars]
        notes = (capture.user_notes or "").strip()
        page_url = capture.page_url or "none"
        asset_names = (
            ", ".join(asset.original_name or asset.path for asset in capture.assets) or "none"
        )

        return f"""
Extract a reviewable ProductDraft from this Mizaaj capture.

Extraction rules:
- If a tag shows regional sizes, keep each regional label separately.
  Example: "UK L / EUR L" becomes size_labels for UK L and EUR L,
  and size_options can include "UK L" and "EUR L".
- Prefer visible title/style/article names. If no product title is visible, return title null.
- Capture SKU, article, style, barcode, fabric composition, care, origin, fit, gender,
  and measurement rows when visible.
- Do not use the image URL or storage path as a fact source. Use "image", "tag",
  "size chart", "care label", "product page", or "manual input".

source_type: {capture.source_type.value}
page_url: {page_url}
asset_names: {asset_names}
user_notes: {notes or "none"}

text_evidence:
{evidence or "none"}
""".strip()

    async def _request_completion(
        self, model: str, content: str | list[dict[str, Any]]
    ) -> dict[str, Any]:
        client = self.client
        if client is not None:
            return await self._post_completion(client, model, content)

        async with httpx.AsyncClient(
            timeout=self.settings.openrouter_timeout_seconds
        ) as scoped_client:
            return await self._post_completion(scoped_client, model, content)

    async def _post_completion(
        self,
        client: httpx.AsyncClient,
        model: str,
        content: str | list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                self._chat_completions_url(),
                headers=self._headers(),
                json=self._payload(model, content),
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            message = self._provider_error_message(exc.response)
            raise ProviderRequestError(message) from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderRequestError("OpenRouter extraction request failed.") from exc

        if not isinstance(data, dict):
            raise ProviderRequestError("OpenRouter returned an unexpected response shape.")
        return data

    def _chat_completions_url(self) -> str:
        return f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": self.settings.openrouter_app_title,
        }
        if self.settings.openrouter_site_url:
            headers["HTTP-Referer"] = self.settings.openrouter_site_url
        return headers

    def _payload(self, model: str, content: str | list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.1,
            "max_tokens": 2400,
            "require_parameters": self.settings.openrouter_require_parameters,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "mizaaj_product_extraction",
                    "strict": True,
                    "schema": PRODUCT_EXTRACTION_SCHEMA,
                },
            },
        }

    def _parse_payload(self, response: dict[str, Any]) -> OpenRouterProductPayload:
        try:
            message = response["choices"][0]["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRequestError(
                "OpenRouter response did not include message content."
            ) from exc

        try:
            parsed = self._coerce_payload_shape(self._json_payload(content))
            return OpenRouterProductPayload.model_validate(parsed)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ProviderRequestError(
                "OpenRouter response could not be parsed as a product draft."
            ) from exc

    def _json_payload(self, content: Any) -> Any:
        if not isinstance(content, str):
            return content

        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(stripped[start : end + 1])

    def _coerce_payload_shape(self, payload: Any) -> Any:
        if not isinstance(payload, dict) or not isinstance(payload.get("product_draft"), dict):
            return payload

        draft = payload["product_draft"]
        brand, title = self._split_brand_title(self._clean(draft.get("title")))
        size_labels = self._coerce_size_label_values(draft.get("size_labels"))
        evidence_claims = self._claims_from_evidence(draft.get("evidence"))
        fit = self._string_list(draft.get("fit"))
        style = self._clean(draft.get("style"))

        return {
            "brand": self._clean(draft.get("brand")) or brand,
            "retailer": self._clean(draft.get("retailer")),
            "title": self._clean(draft.get("product_name")) or title,
            "sku": self._clean(draft.get("sku")),
            "url": self._clean(draft.get("url")),
            "category": self._clean(draft.get("category")) or ClothingCategory.unknown.value,
            "color": self._clean(draft.get("color")),
            "material": self._clean(draft.get("material")),
            "size_options": self._string_list(draft.get("size_options")),
            "size_labels": size_labels,
            "size_chart": self._size_chart_values(draft.get("measurements")),
            "fit_descriptors": self._dedupe([*fit, *([style] if style else [])]),
            "fabric_composition": self._list_or_empty(draft.get("fabric_composition")),
            "care_instructions": self._list_or_empty(draft.get("care_instructions")),
            "origin_country": self._clean(draft.get("origin_country") or draft.get("origin")),
            "gender": self._clean(draft.get("gender")),
            "product_identifiers": self._identifiers_from_legacy_draft(draft),
            "attributes": [],
            "claims": evidence_claims,
        }

    def _coerce_size_label_values(self, value: Any) -> list[dict[str, str | None]]:
        labels = self._string_list(value)
        coerced: list[dict[str, str | None]] = []
        for label in labels:
            parts = label.split(maxsplit=1)
            if len(parts) == 2 and parts[0].upper() in {"UK", "EU", "EUR", "US"}:
                system = "EUR" if parts[0].upper() == "EU" else parts[0].upper()
                coerced.append(
                    {"label": parts[1], "system": system, "region": system, "audience": None}
                )
            else:
                coerced.append({"label": label, "system": None, "region": None, "audience": None})
        return coerced

    def _claims_from_evidence(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        claims: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            field = self._clean(item.get("field"))
            item_value = item.get("value")
            source = self._clean(item.get("source")) or "text_evidence"
            if not field or item_value in (None, [], ""):
                continue
            claims.append(
                {
                    "predicate": field,
                    "value": ", ".join(item_value)
                    if isinstance(item_value, list)
                    else str(item_value),
                    "source": source.replace("_", " "),
                    "confidence": 0.65,
                }
            )
        return claims

    def _identifiers_from_legacy_draft(self, draft: dict[str, Any]) -> list[dict[str, str]]:
        identifiers = []
        for kind in ("sku", "article", "barcode"):
            value = self._clean(draft.get(kind))
            if self._is_real_value(value):
                identifiers.append({"kind": kind, "value": value})
        return identifiers

    def _size_chart_values(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _list_or_empty(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    def _split_brand_title(self, title: str | None) -> tuple[str | None, str | None]:
        if not title:
            return None, None
        words = title.split()
        brand_words: list[str] = []
        for word in words:
            if word[:1].isupper():
                brand_words.append(word)
                continue
            break
        if not brand_words:
            return None, title
        brand = " ".join(brand_words)
        product_title = " ".join(words[len(brand_words) :]).strip() or title
        return brand, product_title

    def _to_product_draft(
        self,
        payload: OpenRouterProductPayload,
        capture: CaptureCreate,
    ) -> ProductDraft:
        source = self._source_for(capture)
        brand = self._clean(payload.brand)
        title = self._clean(payload.title)
        category = self._category(payload.category, self._category_evidence(payload, capture))
        size_labels = self._size_labels(payload.size_labels)
        size_options = self._size_options(payload.size_options, size_labels)
        claims = self._claims(payload, source, brand, title, category, size_options)

        return ProductDraft(
            brand=brand,
            retailer=self._clean(payload.retailer),
            title=title,
            sku=self._clean(payload.sku),
            url=self._clean(payload.url) or capture.page_url,
            category=category,
            color=self._clean(payload.color),
            material=self._clean(payload.material),
            size_options=size_options,
            size_labels=size_labels,
            size_chart=self._size_chart(payload.size_chart),
            fit_descriptors=self._dedupe(payload.fit_descriptors),
            fabric_composition=self._fabric_composition(payload.fabric_composition),
            care_instructions=self._care_instructions(payload.care_instructions),
            origin_country=self._clean(payload.origin_country),
            gender=self._clean(payload.gender),
            product_identifiers=self._product_identifiers(payload.product_identifiers),
            attributes=self._attributes(payload.attributes),
            extracted_claims=claims,
        )

    def _claims(
        self,
        payload: OpenRouterProductPayload,
        source: str,
        brand: str | None,
        title: str | None,
        category: ClothingCategory,
        size_options: list[str],
    ) -> list[ExtractedClaim]:
        subject = " ".join(part for part in [brand, title] if part).strip() or "captured item"
        claims = [
            ExtractedClaim(
                subject=subject,
                predicate=claim.predicate.strip(),
                value=claim.value.strip(),
                source=self._claim_source(claim.source, source),
                confidence=claim.confidence,
            )
            for claim in payload.claims
            if claim.predicate.strip() and claim.value.strip()
        ]

        present = {claim.predicate for claim in claims}
        inferred = {
            "category": category.value if category != ClothingCategory.unknown else None,
            "material": self._clean(payload.material),
            "available_sizes": ", ".join(size_options) if size_options else None,
            "color": self._clean(payload.color),
            "regional_size_labels": self._regional_size_claim(payload.size_labels),
            "fit": ", ".join(self._dedupe(payload.fit_descriptors))
            if payload.fit_descriptors
            else None,
            "fabric_composition": self._composition_claim(payload.fabric_composition),
            "care": self._care_claim(payload.care_instructions),
            "origin_country": self._clean(payload.origin_country),
            "gender": self._clean(payload.gender),
            "product_identifiers": self._identifier_claim(payload.product_identifiers),
        }
        for predicate, value in inferred.items():
            if value and predicate not in present:
                claims.append(
                    ExtractedClaim(
                        subject=subject,
                        predicate=predicate,
                        value=value,
                        source=source,
                        confidence=0.65,
                    )
                )

        return claims

    def _size_options(
        self,
        size_options: list[str],
        size_labels: list[SizeLabel],
    ) -> list[str]:
        observed = [
            " ".join(part for part in [label.system, label.label] if part).strip()
            for label in size_labels
        ]
        return self._dedupe([*size_options, *observed])

    def _size_labels(self, size_labels: list[OpenRouterSizeLabel]) -> list[SizeLabel]:
        normalized: list[SizeLabel] = []
        seen: set[tuple[str | None, str, str | None, str | None]] = set()
        for label in size_labels:
            normalized_label = self._normalized_size_label(label)
            if normalized_label is None:
                continue
            key = (
                normalized_label.system,
                normalized_label.label.lower(),
                normalized_label.region,
                normalized_label.audience,
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append(normalized_label)
        return normalized

    def _normalized_size_label(self, label: OpenRouterSizeLabel) -> SizeLabel | None:
        raw_label = label.label.strip()
        if not raw_label:
            return None

        system = self._clean(label.system)
        region = self._clean(label.region)
        parts = raw_label.split(maxsplit=1)
        if len(parts) == 2 and parts[0].upper() in {"UK", "EU", "EUR", "US"}:
            prefix = "EUR" if parts[0].upper() == "EU" else parts[0].upper()
            if (
                not system
                or system.lower() in {"alpha", "letter", "size", "regional"}
                or system.upper() == prefix
            ):
                system = prefix
                region = region or prefix
                raw_label = parts[1]

        return SizeLabel(
            label=raw_label,
            system=system,
            region=region,
            audience=self._clean(label.audience),
        )

    def _size_chart(self, size_chart: list[OpenRouterSizeSet]) -> list[SizeMeasurementSet]:
        return [
            SizeMeasurementSet(
                size=item.size.strip(),
                measurements=[
                    Measurement(
                        name=measurement.name.strip(),
                        value=measurement.value,
                        unit=measurement.unit.strip() or "cm",
                    )
                    for measurement in item.measurements
                    if measurement.name.strip()
                ],
            )
            for item in size_chart
            if item.size.strip()
        ]

    def _fabric_composition(
        self,
        composition: list[OpenRouterTextileComposition],
    ) -> list[TextileComposition]:
        return [
            TextileComposition(
                material=item.material.strip(),
                percentage=item.percentage,
                component=self._clean(item.component),
            )
            for item in composition
            if item.material.strip()
        ]

    def _care_instructions(
        self,
        instructions: list[OpenRouterCareInstruction],
    ) -> list[CareInstruction]:
        return [
            CareInstruction(
                instruction=item.instruction.strip(),
                category=self._clean(item.category),
            )
            for item in instructions
            if item.instruction.strip()
        ]

    def _product_identifiers(
        self,
        identifiers: list[OpenRouterProductIdentifier],
    ) -> list[ProductIdentifier]:
        return [
            ProductIdentifier(kind=item.kind.strip(), value=item.value.strip())
            for item in identifiers
            if item.kind.strip() and self._is_real_value(item.value)
        ]

    def _attributes(self, attributes: list[OpenRouterProductAttribute]) -> list[ProductAttribute]:
        return [
            ProductAttribute(name=item.name.strip(), value=item.value.strip())
            for item in attributes
            if item.name.strip() and item.value.strip()
        ]

    def _regional_size_claim(self, size_labels: list[OpenRouterSizeLabel]) -> str | None:
        values = self._dedupe(
            [self._size_label_text(label) for label in self._size_labels(size_labels)]
        )
        return ", ".join(values) if values else None

    def _size_label_text(self, label: SizeLabel) -> str:
        prefix = label.system or label.region
        return " ".join(part for part in [prefix, label.label] if part).strip()

    def _composition_claim(
        self,
        composition: list[OpenRouterTextileComposition],
    ) -> str | None:
        values = [
            " ".join(
                part
                for part in [
                    f"{item.percentage:g}%" if item.percentage is not None else None,
                    item.material.strip(),
                    f"({item.component.strip()})" if item.component else None,
                ]
                if part
            )
            for item in composition
            if item.material.strip()
        ]
        return ", ".join(values) if values else None

    def _care_claim(self, instructions: list[OpenRouterCareInstruction]) -> str | None:
        values = [item.instruction.strip() for item in instructions if item.instruction.strip()]
        return ", ".join(values) if values else None

    def _identifier_claim(
        self,
        identifiers: list[OpenRouterProductIdentifier],
    ) -> str | None:
        values = [
            f"{item.kind.strip()} {item.value.strip()}"
            for item in identifiers
            if item.kind.strip() and self._is_real_value(item.value)
        ]
        return ", ".join(values) if values else None

    def _source_for(self, capture: CaptureCreate) -> str:
        if capture.page_url:
            return "product page"
        if capture.assets:
            return "image"
        return "manual input"

    def _claim_source(self, value: str | None, fallback: str) -> str:
        cleaned = self._clean(value) or fallback
        lower = cleaned.lower()
        if "mizaaj-uploads" in lower or "/captures/" in lower:
            return "image"
        if lower.startswith(("http://", "https://")):
            return "product page"
        return cleaned

    def _category(self, value: str | None, evidence: str = "") -> ClothingCategory:
        evidence_category = self._category_from_evidence(evidence)
        if evidence_category is not None:
            return evidence_category

        normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "t_shirt": ClothingCategory.tshirt,
            "tee": ClothingCategory.tshirt,
            "pants": ClothingCategory.trousers,
            "trouser": ClothingCategory.trousers,
            "sneaker": ClothingCategory.shoes,
            "sneakers": ClothingCategory.shoes,
            "coat": ClothingCategory.jacket,
            "blazer": ClothingCategory.jacket,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return ClothingCategory(normalized)
        except ValueError:
            return ClothingCategory.unknown

    def _category_from_evidence(self, evidence: str) -> ClothingCategory | None:
        normalized = evidence.lower().replace("-", " ")
        phrase_matches: tuple[tuple[ClothingCategory, tuple[str, ...]], ...] = (
            (ClothingCategory.tshirt, ("t shirt", "tee shirt", "tee", "airism cotton")),
            (ClothingCategory.jeans, ("jeans", "denim jean")),
            (ClothingCategory.trousers, ("trousers", "pants", "chinos", "cargo pant")),
            (ClothingCategory.dress, ("dress", "gown")),
            (ClothingCategory.jacket, ("jacket", "coat", "blazer", "hoodie")),
            (ClothingCategory.shoes, ("shoes", "sneakers", "boots", "loafers")),
        )
        for category, phrases in phrase_matches:
            if any(phrase in normalized for phrase in phrases):
                return category
        if "shirt" in normalized:
            return ClothingCategory.shirt
        return None

    def _category_evidence(
        self,
        payload: OpenRouterProductPayload,
        capture: CaptureCreate,
    ) -> str:
        claim_text = " ".join(f"{claim.predicate} {claim.value}" for claim in payload.claims)
        attributes = " ".join(f"{item.name} {item.value}" for item in payload.attributes)
        return " ".join(
            part
            for part in [
                payload.title,
                payload.material,
                payload.color,
                *payload.fit_descriptors,
                attributes,
                claim_text,
                *capture.text_blocks,
                capture.user_notes,
            ]
            if part
        )

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            cleaned = value.strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                deduped.append(cleaned)
        return deduped

    def _clean(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    def _is_real_value(self, value: str | None) -> bool:
        cleaned = self._clean(value)
        if cleaned is None:
            return False
        return cleaned.lower() not in {"n/a", "na", "none", "null", "unknown", "not visible"}

    def _provider_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return f"OpenRouter extraction failed with HTTP {response.status_code}."

        error = payload.get("error") if isinstance(payload, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        if message:
            return f"OpenRouter extraction failed: {message}"
        return f"OpenRouter extraction failed with HTTP {response.status_code}."
