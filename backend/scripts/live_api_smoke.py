import argparse
import sys
from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.dependencies import get_extraction_gateway, get_memory_gateway, get_store
from app.main import create_app


def main() -> int:
    args = _args()
    get_settings.cache_clear()
    get_store.cache_clear()
    get_memory_gateway.cache_clear()
    get_extraction_gateway.cache_clear()
    settings = get_settings()

    _print_config(settings)
    if not args.spend_tokens:
        print("Refusing live smoke without --spend-tokens.")
        return 0

    client = TestClient(create_app())
    user_id = _step("auth", lambda: client.get("/api/v1/auth/me").json()["user_id"])

    _step("clean-start", lambda: client.delete(f"/api/v1/memory/users/{user_id}/app-data"))
    _step(
        "profile",
        lambda: client.put(
            f"/api/v1/profiles/{user_id}",
            json={
                "display_name": "Sid",
                "sensitivities": ["clingy fabric", "tight chest"],
                "category_preferences": [
                    {
                        "category": "shirt",
                        "usual_size": "M",
                        "preferred_fit": "relaxed",
                        "notes": "Prefers shoulder room and a soft drape.",
                    }
                ],
            },
        ),
    )

    assets = _step(
        "upload-image" if args.upload_intent and args.image_url else "prepare-assets",
        lambda: _capture_assets(client, user_id, args.image_url, args.upload_intent),
    )

    capture = _step(
        "extract-capture",
        lambda: client.post(
            "/api/v1/captures",
            json={
                "user_id": user_id,
                "source_type": "upload" if args.image_url else "manual",
                "text_blocks": [
                    (
                        "Zara linen blend relaxed shirt. Black. Sizes S M L XL. "
                        "Tag says UK L and EUR L. 55% linen, 45% cotton. "
                        "Machine wash cold. Drop shoulder, relaxed drape."
                    )
                ],
                "assets": assets,
                "user_notes": "Avoid clingy fabric around the chest.",
            },
        ).json(),
    )
    _require(capture["product_draft"]["extracted_claims"], "capture extracted no claims")

    first_ask = _step(
        "ask-unconfirmed-capture",
        lambda: client.post(
            "/api/v1/ask",
            json={
                "user_id": user_id,
                "capture_id": capture["id"],
                "question": "Should I start with M or L, and what should Mizaaj remember?",
                "context_notes": "Avoid clingy fabric around the chest.",
            },
        ).json(),
    )
    _require(first_ask["memory_drafts"], "ask generated no memory drafts")
    deletion_marker = "Mizaaj smoke deletion marker: cobalt collar lining pinches the neck."

    remembered = _step(
        "remember-chat",
        lambda: client.post(
            "/api/v1/ask/remember",
            json={
                "user_id": user_id,
                "capture_id": capture["id"],
                "question": first_ask["question"],
                "answer": first_ask["answer"],
                "drafts": [
                    *first_ask["memory_drafts"][:3],
                    {
                        "kind": "fit_preference",
                        "subject": "smoke deletion marker",
                        "text": deletion_marker,
                        "confidence": 0.95,
                        "tags": ["smoke", "delete-me"],
                    },
                ],
                "evidence": first_ask["evidence"],
                "recalled_facts": first_ask["recalled_facts"],
            },
        ).json(),
    )
    _require(remembered["memory_status"] == "indexed", "chat memory was not indexed")
    _require(remembered["memory_record"], "chat memory record was not returned")
    memory_record_id = remembered["memory_record"]["id"]

    confirmed = _step(
        "confirm-capture",
        lambda: client.post(
            f"/api/v1/captures/{capture['id']}/confirm",
            json={
                "product_draft": capture["product_draft"],
                "accepted_claim_ids": [
                    claim["id"] for claim in capture["product_draft"]["extracted_claims"]
                ],
            },
        ).json(),
    )
    _require(confirmed["confirmed"], "capture was not confirmed")
    product_id = confirmed["product_snapshot"]["id"]

    purchase = _step(
        "purchase-outcome",
        lambda: client.post(
            "/api/v1/purchases",
            json={
                "user_id": user_id,
                "product_id": product_id,
                "purchased_size": "M",
                "outcome": "kept",
                "fit_rating": 5,
                "comfort_rating": 4,
                "silhouette_rating": 5,
                "fit_notes": "Size M had enough shoulder room and did not cling.",
            },
        ).json(),
    )
    updated_purchase = _step(
        "update-outcome",
        lambda: client.patch(
            f"/api/v1/purchases/{purchase['id']}",
            json={
                "fit_rating": 4,
                "comfort_rating": 5,
                "fit_notes": "Updated after a second wear: shoulder room stayed good.",
            },
        ).json(),
    )
    _require(updated_purchase["fit_rating"] == 4, "purchase update did not persist")

    final_ask = _step(
        "ask-after-outcome",
        lambda: client.post(
            "/api/v1/ask",
            json={
                "user_id": user_id,
                "product_id": product_id,
                "question": "What should I buy next time from this kind of shirt?",
            },
        ).json(),
    )
    _require(final_ask["evidence"], "final ask returned no evidence")

    recall = _step(
        "recall",
        lambda: client.post(
            "/api/v1/memory/recall",
            json={"user_id": user_id, "query": "clingy fabric shoulder room", "top_k": 5},
        ).json(),
    )
    _require(recall["status"] == "ready", f"recall degraded: {recall.get('error')}")
    _require(recall["facts"], "recall returned no facts")

    deleted_memory = _step(
        "delete-saved-memory",
        lambda: client.delete(f"/api/v1/ask/memories/{memory_record_id}").json(),
    )
    _require(deleted_memory["id"] == memory_record_id, "deleted memory id mismatch")

    deleted_recall = _step(
        "recall-after-memory-delete",
        lambda: client.post(
            "/api/v1/memory/recall",
            json={"user_id": user_id, "query": deletion_marker, "top_k": 5},
        ).json(),
    )
    _require(
        deleted_recall["status"] == "ready",
        f"post-delete recall degraded: {deleted_recall.get('error')}",
    )
    recalled_text = " ".join(fact["text"].lower() for fact in deleted_recall["facts"])
    _require("cobalt collar lining" not in recalled_text, "deleted memory still recalled")

    deleted_purchase = _step(
        "delete-outcome",
        lambda: client.delete(f"/api/v1/purchases/{purchase['id']}").json(),
    )
    _require(deleted_purchase["id"] == purchase["id"], "deleted purchase id mismatch")

    if args.cleanup_end:
        _step("clean-end", lambda: client.delete(f"/api/v1/memory/users/{user_id}/app-data"))

    print("Live smoke completed.")
    return 0


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spend-tokens", action="store_true")
    parser.add_argument("--upload-intent", action="store_true")
    parser.add_argument("--cleanup-end", action="store_true")
    parser.add_argument("--image-url")
    return parser.parse_args()


def _print_config(settings) -> None:
    print("Mizaaj live smoke config")
    print(f"  store_provider={settings.store_provider}")
    print(f"  memory_provider={settings.memory_provider}")
    print(f"  extraction_provider={settings.extraction_provider}")
    print(f"  openrouter_key_set={bool(settings.openrouter_api_key)}")
    print(f"  cognee_cloud_key_set={bool(settings.cognee_cloud_api_key)}")
    print(f"  s3_endpoint_set={bool(settings.s3_endpoint_url)}")


def _image_assets(image_url: str | None) -> list[dict[str, str]]:
    if not image_url:
        return []
    return [
        {
            "path": image_url,
            "mime_type": "image/jpeg",
            "original_name": "web-smoke-image.jpg",
            "public_url": image_url,
        }
    ]


def _capture_assets(
    client: TestClient, user_id: str, image_url: str | None, upload_intent: bool
) -> list[dict[str, str]]:
    if not image_url:
        return []
    if not upload_intent:
        return _image_assets(image_url)

    intent = client.post(
        "/api/v1/uploads/intent",
        json={
            "user_id": user_id,
            "file_name": "mizaaj-smoke-tag.jpg",
            "content_type": "image/jpeg",
        },
    )
    if intent.status_code >= 400:
        raise RuntimeError(intent.text)
    upload = intent.json()

    with httpx.Client(timeout=30) as http:
        source = http.get(image_url)
        source.raise_for_status()
        put = http.put(
            upload["upload_url"],
            content=source.content,
            headers={"Content-Type": "image/jpeg"},
        )
        put.raise_for_status()
        if upload.get("public_url"):
            readable = http.get(upload["public_url"])
            readable.raise_for_status()

    return [
        {
            "path": upload["path"],
            "mime_type": "image/jpeg",
            "original_name": "mizaaj-smoke-tag.jpg",
            "public_url": upload["public_url"],
        }
    ]


def _step(label: str, action: Callable[[], Any]) -> Any:
    print(f"[{label}] start")
    result = action()
    if hasattr(result, "status_code"):
        response = result
        print(f"[{label}] status={response.status_code}")
        if response.status_code >= 400:
            print(response.text)
            sys.exit(1)
        return response.json()
    print(f"[{label}] ok")
    return result


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


if __name__ == "__main__":
    raise SystemExit(main())
