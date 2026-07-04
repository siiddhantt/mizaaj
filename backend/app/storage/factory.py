from app.core.config import Settings
from app.storage.in_memory import InMemoryStore
from app.storage.postgres import PostgresStore
from app.storage.store import MizaajStore


def create_store(settings: Settings) -> MizaajStore:
    if settings.store_provider == "postgres":
        store = PostgresStore(settings)
    elif settings.store_provider == "memory":
        store = InMemoryStore()
    else:
        raise ValueError(f"Unsupported store provider: {settings.store_provider}")

    store.initialize()
    return store
