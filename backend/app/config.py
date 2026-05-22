from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os

# Optional proxy support — set via environment variables if your server requires a proxy
_http_proxy = os.environ.get("HTTP_PROXY", "")
_https_proxy = os.environ.get("HTTPS_PROXY", "")
_no_proxy = os.environ.get("NO_PROXY", "localhost,127.0.0.1")
if _http_proxy:
    os.environ["HTTP_PROXY"] = _http_proxy
if _https_proxy:
    os.environ["HTTPS_PROXY"] = _https_proxy
os.environ.setdefault("NO_PROXY", _no_proxy)


class Settings(BaseSettings):
    # LLM provider — defaults to OpenRouter (OpenAI-compatible)
    llm_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="openai/gpt-4o-mini", alias="LLM_MODEL")
    llm_max_tokens: int = Field(default=16384, alias="LLM_MAX_TOKENS")

    # Optional OpenRouter HTTP headers
    openrouter_site_url: str = Field(default="", alias="OPENROUTER_SITE_URL")
    openrouter_site_name: str = Field(default="Draft Document AI Agent", alias="OPENROUTER_SITE_NAME")

    # Embedding
    embedding_model: str = Field(default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # Storage
    chroma_mode: str = Field(default="local", alias="CHROMA_MODE")        # local | cloud | http
    chroma_db_path: str = Field(default="./data/chroma_db", alias="CHROMA_DB_PATH")
    # Chroma Cloud (CHROMA_MODE=cloud) — https://cloud.trychroma.com
    chroma_cloud_api_key: str = Field(default="", alias="CHROMA_CLOUD_API_KEY")
    chroma_cloud_tenant: str = Field(default="", alias="CHROMA_CLOUD_TENANT")
    chroma_cloud_database: str = Field(default="default_database", alias="CHROMA_CLOUD_DATABASE")
    # Self-hosted ChromaDB server (CHROMA_MODE=http)
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")
    documents_path: str = Field(default="./data/documents", alias="DOCUMENTS_PATH")
    export_path: str = Field(default="./data/exports", alias="EXPORT_PATH")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    allowed_origins: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")

    model_config = {"env_file": ".env", "populate_by_name": True}

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
