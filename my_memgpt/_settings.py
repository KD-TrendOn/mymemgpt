from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
load_dotenv()

class Settings(BaseSettings):
    pg_connection: str = os.getenv("PG_CONNECTION")
    pg_collection_name: str = os.getenv("PG_COLLECTION_NAME")
    model: str = "openai/gpt-4o"
    model_provider: str = "openai"
    openai_api_key:Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_base_provider:Optional[str] = os.getenv("OPENAI_BASE_PROVIDER")
    langchain_tracing_v2:str = 'true'
    langchain_endpoint:Optional[str] = os.getenv("LANGCHAIN_ENDPOINT")
    langchain_api_key:Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    langchain_project:Optional[str] = os.getenv("LANGCHAIN_PROJECT")
    device:str = "cpu"
    embeddings_model:str = "cointegrated/LaBSE-en-ru"
    tavily_api_key:str = os.getenv("TAVILY_API_KEY")


SETTINGS = Settings()
