from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pg_connection = "postgresql+psycopg://langchain:langchain@localhost:6024/langchain"
    pg_collection_name = "my_memgpt"
    model: str = "openai/gpt-4o"
    device:str = "cpu"
    embeddings_model:str = "cointegrated/LaBSE-en-ru"


SETTINGS = Settings()
