from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB
    postgres_user: str = "prostor"
    postgres_password: str = "prostor"
    postgres_db: str = "prostor"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: str = "postgresql+asyncpg://prostor:prostor@localhost:5432/prostor"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket_templates: str = "prostor-tz-templates"
    minio_bucket_exports: str = "prostor-exports"
    minio_bucket_attachments: str = "prostor-attachments"
    minio_bucket_ingest: str = "prostor-ingest"

    # LLM (DeepSeek)
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_reasoner_model: str = "deepseek-reasoner"
    llm_use_reasoner_for_analysis: bool = False
    llm_use_reasoner_for_report: bool = True

    # Embeddings
    embeddings_provider: str = "local"
    embeddings_model: str = "intfloat/multilingual-e5-base"
    llm_embedding_dim: int = 768
    embeddings_api_base: str = "https://api.openai.com/v1"
    embeddings_api_key: str = ""

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    use_celery: bool = False

    # Auth
    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    jwt_ttl_hours: int = 24

    # App
    env: str = "development"
    cors_origins: str = "http://localhost:3000"
    seed_on_start: bool = True
    seed_xlsx_dir: str = "seed/xlsx"
    seed_tz_templates_dir: str = "seed/tz_templates"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
