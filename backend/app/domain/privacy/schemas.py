from pydantic import BaseModel


class UserDataDeletionResult(BaseModel):
    profile_deleted: bool = False
    captures_deleted: int = 0
    products_deleted: int = 0
    purchases_deleted: int = 0
    saved_memories_deleted: int = 0
    cognee_memory_deleted: bool = False
