from typing import Literal

from pydantic import BaseModel, Field

from app.domain.memory.schemas import MemoryContextFact


class AtlasRecallRequest(BaseModel):
    query: str
    top_k: int = Field(default=4, ge=1, le=10)


class AtlasContext(BaseModel):
    query: str
    facts: list[MemoryContextFact] = Field(default_factory=list)
    status: Literal["ready", "degraded", "disabled"] = "ready"
    error: str | None = None

    @classmethod
    def disabled(cls, query: str) -> "AtlasContext":
        return cls(query=query, status="disabled")

    @classmethod
    def degraded(cls, query: str, error: str) -> "AtlasContext":
        return cls(query=query, status="degraded", error=error)
