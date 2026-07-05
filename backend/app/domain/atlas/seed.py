import json
import re
from pathlib import Path
from typing import Any

from app.domain.atlas.gateway import AtlasGateway
from app.domain.atlas.schemas import AtlasContext, AtlasRecallRequest
from app.domain.memory.schemas import MemoryContextFact

DEFAULT_ATLAS_SEED = Path(__file__).resolve().parents[3] / "data" / "mizaaj_atlas_seed_v2.json"


class SeedAtlasGateway(AtlasGateway):
    def __init__(self, seed_path: Path = DEFAULT_ATLAS_SEED):
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        self.records: list[dict[str, Any]] = payload["records"]

    async def recall_public(self, request: AtlasRecallRequest) -> AtlasContext:
        terms = _terms(request.query)
        scored = [
            (score, record)
            for record in self.records
            if (score := _score_record(record, terms)) > 0
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        facts = [
            MemoryContextFact(
                text=_record_summary(record),
                source=f"mizaaj_atlas:{record['id']}",
                score=float(score),
            )
            for score, record in scored[: request.top_k]
        ]
        return AtlasContext(query=request.query, facts=facts)


def _terms(value: str) -> set[str]:
    return {
        term
        for term in re.split(r"[^a-z0-9&]+", value.lower())
        if len(term) > 2 and term not in {"the", "and", "for", "with", "should"}
    }


def _score_record(record: dict[str, Any], terms: set[str]) -> int:
    identity = record["identity"]
    weighted_text = " ".join(
        [
            identity.get("brand") or "",
            identity.get("retailer") or "",
            identity.get("title") or "",
            identity.get("category") or "",
            identity.get("style_number") or "",
            identity.get("color") or "",
            " ".join(record.get("tags", [])),
        ]
    ).lower()
    details = json.dumps(
        [record.get("source_facts", []), record.get("derived_rules", [])],
        ensure_ascii=False,
    ).lower()
    return sum(3 for term in terms if term in weighted_text) + sum(
        1 for term in terms if term in details
    )


def _record_summary(record: dict[str, Any]) -> str:
    identity = record["identity"]
    facts = "; ".join(f"{fact['field']}: {fact['value']}" for fact in record["source_facts"][:4])
    rules = "; ".join(rule["value"] for rule in record["derived_rules"][:2])
    title = " - ".join(part for part in [identity.get("brand"), identity.get("title")] if part)
    return (
        f"{title}. Public Atlas evidence: {facts}. "
        f"Non-personal interpretation: {rules}. Source: {identity['canonical_url']}"
    )
