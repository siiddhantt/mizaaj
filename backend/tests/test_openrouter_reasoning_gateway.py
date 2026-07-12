import json
from uuid import UUID

import httpx
import pytest

from app.core.config import Settings
from app.domain.ask.schemas import AskEvidence, ConversationRole, ConversationTurn
from app.domain.products.schemas import ProductSnapshot
from app.domain.profiles.schemas import FitProfile
from app.domain.reasoning.openrouter import OpenRouterReasoningGateway
from app.domain.reasoning.schemas import GroundedReasoningRequest

USER_ID = UUID("00000000-0000-4000-8000-000000000001")


@pytest.mark.asyncio
async def test_reasoning_uses_strict_grounded_output_and_canonical_subjects():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer_markdown": (
                                        "Your saved outcome supports **L**; check the chest row."
                                    ),
                                    "confidence": 0.84,
                                    "used_evidence_sources": ["purchase:1"],
                                    "memory_drafts": [
                                        {
                                            "kind": "fit_preference",
                                            "scope": "product",
                                            "text": (
                                                "User prefers the relaxed chest fit of this tee."
                                            ),
                                            "confidence": 0.91,
                                            "tags": ["signal:chest_fit"],
                                        }
                                    ],
                                    "outcome_draft": {
                                        "purchased_size": "L",
                                        "outcome": "kept",
                                        "fit_rating": 5,
                                        "comfort_rating": 4,
                                        "silhouette_rating": 5,
                                        "fit_notes": "Relaxed chest fit without cling.",
                                        "confidence": 0.88,
                                    },
                                }
                            )
                        }
                    }
                ]
            },
        )

    product = ProductSnapshot(title="Relaxed tee", brand="Puma")
    gateway = OpenRouterReasoningGateway(
        Settings(openrouter_api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    result = await gateway.synthesize(
        GroundedReasoningRequest(
            user_id=USER_ID,
            question="I kept L and liked the chest fit. What did we learn?",
            conversation=[
                ConversationTurn(role=ConversationRole.user, content="This is a Puma tee")
            ],
            profile=FitProfile(user_id=USER_ID, display_name="Sid"),
            product=product,
            evidence=[AskEvidence(label="Saved outcome", detail="L was kept", source="purchase:1")],
        )
    )

    assert result.answer.startswith("Your saved outcome")
    assert result.memory_drafts[0].subject == f"product:{product.id}:fit_preference"
    assert f"product:{product.id}" in result.memory_drafts[0].tags
    assert result.outcome_draft is not None
    assert result.outcome_draft.purchased_size == "L"
    assert captured["temperature"] == 0.15
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert "confirmed_outcomes" in captured["messages"][1]["content"]
