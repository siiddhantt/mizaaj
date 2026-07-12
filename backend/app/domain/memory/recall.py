import re
from collections.abc import Mapping
from typing import Any

from app.domain.memory.schemas import MemoryContextFact


def recall_item_to_fact(item: Any, source: str) -> MemoryContextFact:
    return MemoryContextFact(
        text=clean_recall_text(_recall_text(item)),
        source=source,
        score=_recall_score(item),
    )


def clean_recall_text(value: str) -> str:
    text = (
        value.replace("\\n", " ").replace("\\'", "'").replace('\\"', '"').replace("**", "").strip()
    )
    node_contents = re.findall(
        r"__node_content_start__\s*(.*?)\s*__node_content_end__",
        text,
        flags=re.I | re.S,
    )
    if node_contents:
        text = " ".join(dict.fromkeys(item.strip() for item in node_contents if item.strip()))
    text = re.split(r"\bEvidence:\s*", text, maxsplit=1, flags=re.I)[0]
    text = _extract_chunk_text(text) or text
    text = re.sub(r"\b(?:document|data_id|chunk_id)\s*:?\s*[0-9a-f-]{24,}\b", "", text, flags=re.I)
    text = re.sub(r"\bchunk\s+\d+\s+of\s+document\s+[0-9a-f-]{24,}\b:?", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _recall_text(item: Any) -> str:
    if isinstance(item, Mapping):
        for key in ("context", "answer", "text", "value", "content"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value

        raw = item.get("raw")
        if isinstance(raw, Mapping):
            for key in ("value", "text", "answer", "content"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value

    return str(item)


def _recall_score(item: Any) -> float | None:
    if not isinstance(item, Mapping):
        return None

    value = item.get("score")
    return value if isinstance(value, float | int) else None


def _extract_chunk_text(value: str) -> str | None:
    match = re.search(
        "chunk\\s+\\d+\\s+of\\s+document\\s+[0-9a-f-]{24,}.*?:"
        "\\s*[\\\"'\\u201c](.+?)[\\\"'\\u201d](?:\\s*$|\\s+-\\s+chunk)",
        value,
        flags=re.I | re.S,
    )
    return match.group(1).strip() if match else None
