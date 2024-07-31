
from functools import lru_cache

import langsmith
from langchain_core.runnables import RunnableConfig
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import PGVector


from my_memgpt import _schemas as schemas
from my_memgpt import _settings as settings

_DEFAULT_DELAY = 60  # seconds

@langsmith.traceable
def ensure_configurable(config: RunnableConfig) -> schemas.GraphConfig:
    """Merge the user-provided config with default values."""
    configurable = config.get("configurable", {})
    return {
        **configurable,
        **schemas.GraphConfig(
            delay=configurable.get("delay", _DEFAULT_DELAY),
            model=configurable.get("model", settings.SETTINGS.model),
            thread_id="1",
            user_id="2",
        ),
    }

@lru_cache
def get_vectorstore() -> PGVector:
    embeddings = HuggingFaceEmbeddings(model_name=settings.SETTINGS.embeddings_model, model_kwargs={"device":settings.SETTINGS.device})
    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name=settings.SETTINGS.pg_collection_name,
        connection=settings.SETTINGS.pg_connection,
        use_jsonb=True,
        async_mode=True,
    )
    return vectorstore

__all__ = ["ensure_configurable"]