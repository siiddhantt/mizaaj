from uuid import UUID

from app.domain.ask.schemas import MemoryDraft


def canonicalize_memory_draft(
    draft: MemoryDraft,
    product_id: UUID | None,
) -> MemoryDraft:
    if product_id is None:
        return draft
    subject = draft.subject
    if subject.startswith("product:"):
        parts = subject.split(":", 2)
        subject = f"product:{product_id}" + (f":{parts[2]}" if len(parts) == 3 else "")
    tags = [f"product:{product_id}" if tag.startswith("product:") else tag for tag in draft.tags]
    return draft.model_copy(update={"subject": subject, "tags": list(dict.fromkeys(tags))})


def memory_draft_text(draft: MemoryDraft) -> str:
    return f"Memory subject: {draft.subject}. {draft.text}"
