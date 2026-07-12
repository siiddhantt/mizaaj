import json
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderNotConfiguredError, ProviderRequestError
from app.domain.ask.schemas import MemoryDraft, OutcomeDraft
from app.domain.reasoning.gateway import ReasoningGateway
from app.domain.reasoning.schemas import (
    GroundedReasoningRequest,
    GroundedReasoningResult,
    ReasoningPayload,
)

SYSTEM_PROMPT = """
You are Mizaaj, a private clothing fit-memory assistant.

Answer the user's actual intent using only the supplied JSON context. Be conversational, concise,
specific, and honest about uncertainty. Never invent measurements, purchases, preferences, product
identity, or fit outcomes. Do not recommend the middle available size merely because it exists.

Evidence priority:
1. Confirmed outcome for the exact product.
2. Confirmed outcomes for the same brand, category, and comparable fit.
3. Explicit user profile and user-authored private memories.
4. Current item facts and product-specific measurements.
5. Source-labeled Mizaaj Atlas evidence.

When evidence conflicts, explain the conflict and prefer the higher-priority source. Atlas is public
evidence, never the user's experience. If a size recommendation is unsupported, say what measurement
or comparison is needed instead of guessing. If the user is reporting a try-on experience, respond
to that experience rather than giving generic buying advice.

Propose memory drafts only for durable facts explicitly stated by the user or directly visible in
the current product evidence. Never turn your own advice, Atlas facts, or uncertainty into a user
preference. Use product scope only when the memory belongs to the active product. Propose an outcome
only when the user clearly says they bought, tried, wore, kept, returned, exchanged, or altered it.
Use null ratings when the user did not provide enough information to score them.

Never claim that a memory or outcome has already been saved. The user must approve the proposals
in the next UI step. Use fit_outcome for a stated try-on result, fit_preference for an explicitly
stated durable preference, and product_fact only for objective product evidence.

Return strict JSON matching the provided schema. Markdown is allowed only inside answer_markdown.
""".strip()


class OpenRouterReasoningGateway(ReasoningGateway):
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.openrouter_api_key:
            raise ProviderNotConfiguredError("OpenRouter API key is required for grounded answers")
        self.settings = settings
        self.transport = transport

    async def synthesize(self, request: GroundedReasoningRequest) -> GroundedReasoningResult:
        response = await self._request(self._payload(request))
        payload = self._parse(response)
        product_id = request.product.id if request.product else None
        drafts = [
            MemoryDraft(
                kind=item.kind,
                subject=(
                    f"product:{product_id}:{item.kind.value}"
                    if item.scope == "product" and product_id
                    else f"user:{request.user_id}:{item.kind.value}"
                ),
                text=item.text,
                confidence=item.confidence,
                tags=self._tags(item.tags, request, item.scope),
            )
            for item in payload.memory_drafts
            if item.scope == "user" or product_id is not None
        ]
        outcome = (
            OutcomeDraft.model_validate(payload.outcome_draft.model_dump())
            if payload.outcome_draft
            else None
        )
        return GroundedReasoningResult(
            answer=payload.answer_markdown.strip(),
            confidence=payload.confidence,
            used_evidence_sources=payload.used_evidence_sources,
            memory_drafts=drafts,
            outcome_draft=outcome,
        )

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": self.settings.openrouter_app_title,
        }
        if self.settings.openrouter_site_url:
            headers["HTTP-Referer"] = self.settings.openrouter_site_url
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.openrouter_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderRequestError(self._error_message(exc.response)) from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ProviderRequestError("OpenRouter reasoning request failed.") from exc
        if not isinstance(result, dict):
            raise ProviderRequestError("OpenRouter returned an unexpected reasoning response.")
        return result

    def _payload(self, request: GroundedReasoningRequest) -> dict[str, Any]:
        context = {
            "question": request.question,
            "context_notes": request.context_notes,
            "conversation": [turn.model_dump(mode="json") for turn in request.conversation[-10:]],
            "profile": request.profile.model_dump(mode="json"),
            "active_product": request.product.model_dump(mode="json") if request.product else None,
            "confirmed_outcomes": [item.model_dump(mode="json") for item in request.purchases],
            "evidence": [item.model_dump(mode="json") for item in request.evidence],
        }
        return {
            "model": self.settings.openrouter_text_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context, ensure_ascii=True)},
            ],
            "temperature": 0.15,
            "max_tokens": 1800,
            "require_parameters": self.settings.openrouter_require_parameters,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "mizaaj_grounded_answer",
                    "strict": True,
                    "schema": ReasoningPayload.model_json_schema(),
                },
            },
        }

    def _parse(self, response: dict[str, Any]) -> ReasoningPayload:
        try:
            content = response["choices"][0]["message"]["content"]
            if isinstance(content, str):
                content = json.loads(content)
            return ReasoningPayload.model_validate(content)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderRequestError("OpenRouter returned an invalid grounded answer.") from exc

    def _tags(self, tags: list[str], request: GroundedReasoningRequest, scope: str) -> list[str]:
        required = ["source:ask", f"kind:{scope}"]
        if scope == "product" and request.product:
            required.extend(
                [
                    f"product:{request.product.id}",
                    f"brand:{(request.product.brand or 'unknown').lower()}",
                    f"category:{request.product.category.value}",
                ]
            )
        normalized = [tag.strip().lower() for tag in [*required, *tags] if tag.strip()]
        return list(dict.fromkeys(normalized))[:10]

    def _error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message")
            if isinstance(message, str) and message.strip():
                return f"OpenRouter reasoning failed: {message.strip()}"
        except (ValueError, AttributeError):
            pass
        return f"OpenRouter reasoning failed with status {response.status_code}."
