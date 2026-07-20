from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gemini
    google_api_key: str

    # SigNoz — OpenTelemetry
    otel_service_name: str = "agentlens"
    otlp_endpoint: str = "https://ingest.in.signoz.cloud:443"
    signoz_ingestion_key: str

    # Tavily
    tavily_api_key: str

    # App
    app_env: str = "development"        # prod: set to "production" on Render dashboard
    frontend_url: str = "http://localhost:5173"  # prod: set to deployed Vercel URL on Render dashboard

    # DB
    database_url: str = ""              # local: empty → SQLite; prod: Supabase Postgres URL on Render dashboard
    sqlite_db_path: str = "./data/agentlens.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    # RAG — vector store
    chroma_path: str = "./data/chroma"
    pinecone_api_key: str = ""          # prod: set on Render dashboard
    pinecone_index_name: str = "agentlens-rag"

    # Auth — JWT
    jwt_secret_key: str                
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7   # 7 days

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()