from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
import os

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
# All persistent state lives under <backend>/{data,uploads,models,...} by
# default so the project runs out of the box on macOS / Linux / Windows
# without Docker. Docker (or any other host) can override each path via the
# matching environment variable (KF_DATA_DIR, KF_MODELS_DIR, etc.) — the
# Dockerfile sets these to /app/... for backwards compatibility.

_BACKEND_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _resolve_dir(env_var: str, default_subdir: str) -> str:
    """Return a path from ``env_var`` if set, else ``<backend>/<default_subdir>``."""
    value = os.environ.get(env_var)
    if value:
        return value
    return os.path.join(_BACKEND_ROOT, default_subdir)


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Knowledge Fabric"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database Configuration
    DATABASE_URL: Optional[str] = None
    PLATFORM_DB_PATH: str = os.path.join(
        _resolve_dir("KF_DATA_DIR", "data"), "weave_platform.db"
    )

    # Graph & retrieval (Phases 3–4)
    USE_GRAPH_RETRIEVAL: bool = os.environ.get("USE_GRAPH_RETRIEVAL", "false").lower() in (
        "1", "true", "yes",
    )
    GRAPH_STORAGE_BACKEND: str = os.environ.get("GRAPH_STORAGE_BACKEND", "postgres")
    NEO4J_URI: Optional[str] = os.environ.get("NEO4J_URI")
    NEO4J_USER: Optional[str] = os.environ.get("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: Optional[str] = os.environ.get("NEO4J_PASSWORD")
    STARDOG_ENDPOINT: Optional[str] = os.environ.get("STARDOG_ENDPOINT")
    STARDOG_DATABASE: Optional[str] = os.environ.get("STARDOG_DATABASE")
    STARDOG_USERNAME: Optional[str] = os.environ.get("STARDOG_USERNAME")
    STARDOG_PASSWORD: Optional[str] = os.environ.get("STARDOG_PASSWORD")

    # Job worker
    ENABLE_JOB_WORKER: bool = os.environ.get("ENABLE_JOB_WORKER", "true").lower() in (
        "1", "true", "yes",
    )
    JOB_POLL_INTERVAL_SECONDS: float = float(os.environ.get("JOB_POLL_INTERVAL_SECONDS", "2"))

    # Vector Database Configuration
    CHROMA_PERSIST_DIRECTORY: str = _resolve_dir("KF_CHROMA_DIR", "chroma_db")

    # Model Configuration
    MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # ----- Storage roots (used by knowledge / ontology / training / models) -----
    # Persistent JSON state (fabrics.json, trained_models.json, …).
    DATA_DIR: str = _resolve_dir("KF_DATA_DIR", "data")
    # Trained / fine-tuned model artifacts.
    MODELS_DIR: str = _resolve_dir("KF_MODELS_DIR", "models")

    # File Upload Configuration
    UPLOAD_DIR: str = _resolve_dir("KF_UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    # Comma-separated in .env (e.g. .pdf,.txt,.docx) — not a JSON list field.
    ALLOWED_EXTENSIONS_RAW: str = Field(
        default=".pdf,.txt,.docx,.xml",
        validation_alias="ALLOWED_EXTENSIONS",
    )

    @property
    def ALLOWED_EXTENSIONS(self) -> list[str]:
        return [part.strip() for part in self.ALLOWED_EXTENSIONS_RAW.split(",") if part.strip()]

    # Ontology Discovery Configuration (own uploads, not shared with Knowledge Fabric)
    ONTOLOGY_DATA_DIR: str = _resolve_dir("KF_ONTOLOGY_DATA_DIR", "ontology_data")
    ONTOLOGY_UPLOAD_DIR: str = _resolve_dir(
        "KF_ONTOLOGY_UPLOAD_DIR", os.path.join("ontology_data", "uploads")
    )
    ONTOLOGY_LLM_MODEL: str = "gpt-4"
    ONTOLOGY_LLM_TEMPERATURE: float = 0.2
    ONTOLOGY_MAX_RETRIES: int = 3
    # Scaling for high volume (millions of records): cap per run to avoid OOM/timeouts
    ONTOLOGY_MAX_ARTIFACTS_PER_RUN: int = 0  # 0 = no limit; set e.g. 100–500 for large catalogs
    ONTOLOGY_MAX_CHUNKS_TOTAL: int = 0  # 0 = no limit; cap total text chunks used in classification/relations
    ONTOLOGY_MAX_CHUNKS_FOR_LLM: int = 10  # max chunks sent to LLM per run (cost/latency)
    
    # Security Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Training Configuration
    BATCH_SIZE: int = 32
    LEARNING_RATE: float = 2e-5
    NUM_EPOCHS: int = 3
    
    # API Keys Configuration
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # AWS Bedrock (optional — enable for enterprise AWS deployments)
    AWS_REGION: str = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    BEDROCK_ENABLED: bool = os.environ.get("BEDROCK_ENABLED", "false").lower() in (
        "1", "true", "yes", "on",
    )
    BEDROCK_MODEL_ID: str = os.environ.get(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    BEDROCK_ONTOLOGY_MODEL_ID: Optional[str] = os.environ.get("BEDROCK_ONTOLOGY_MODEL_ID")

    # LLM Provider Configuration
    DEFAULT_LLM_PROVIDER: str = os.environ.get("DEFAULT_LLM_PROVIDER", "openai")
    ONTOLOGY_LLM_PROVIDER: Optional[str] = os.environ.get("ONTOLOGY_LLM_PROVIDER")
    OPENAI_QUERY_MODEL: str = os.environ.get("OPENAI_QUERY_MODEL", "gpt-4")
    ENABLED_LLM_PROVIDERS_RAW: str = Field(
        default="openai,bedrock",
        validation_alias="ENABLED_LLM_PROVIDERS",
    )

    @property
    def ENABLED_LLM_PROVIDERS(self) -> list[str]:
        return [part.strip() for part in self.ENABLED_LLM_PROVIDERS_RAW.split(",") if part.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

# Create necessary directories
for _d in (
    settings.UPLOAD_DIR,
    settings.CHROMA_PERSIST_DIRECTORY,
    settings.ONTOLOGY_DATA_DIR,
    settings.ONTOLOGY_UPLOAD_DIR,
    settings.DATA_DIR,
    settings.MODELS_DIR,
):
    os.makedirs(_d, exist_ok=True)
