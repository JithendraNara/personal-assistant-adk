"""
Shared configuration — loads workspace identity files + environment.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root
WORKSPACE_DIR = BASE_DIR / "workspace"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# ─── Model Configuration ─────────────────────────────────────────────────────
# Supports ANY provider via LiteLLM. Format: "provider/model-name"
#   Gemini (default):  gemini-2.0-flash, gemini-1.5-pro
#   OpenAI:            openai/gpt-4o, openai/gpt-4o-mini
#   Anthropic:         anthropic/claude-sonnet-4-20250514
#   MiniMax:           minimax/MiniMax-M2.5
#   Ollama (local):    ollama/llama3, ollama/mistral
#   Any LiteLLM model: https://docs.litellm.ai/docs/providers
#
# Set the corresponding API key in .env:
#   Gemini    → GOOGLE_API_KEY
#   OpenAI    → OPENAI_API_KEY
#   Anthropic → ANTHROPIC_API_KEY
#   MiniMax   → MINIMAX_API_KEY (+ MINIMAX_API_BASE=https://api.minimax.io/v1)
#   Ollama    → no key needed (local)

_DEFAULT_MODEL_STR = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")
_REASONING_MODEL_STR = os.getenv("REASONING_MODEL", "gemini-2.0-flash")


def _resolve_model(model_string: str):
    """
    Resolve a model string to the correct ADK model object.
    
    - Gemini models (no '/' prefix or 'gemini' prefix) → pass as plain string
    - Everything else (openai/..., anthropic/..., ollama/...) → wrap with LiteLlm
    """
    # Gemini models work natively with ADK — no wrapper needed
    if '/' not in model_string or model_string.startswith('gemini'):
        return model_string
    
    # All other providers go through LiteLLM
    try:
        from google.adk.models.lite_llm import LiteLlm
        return LiteLlm(model=model_string)
    except ImportError:
        raise ImportError(
            f"Model '{model_string}' requires LiteLLM. Install it with: pip install litellm"
        )


DEFAULT_MODEL = _resolve_model(_DEFAULT_MODEL_STR)
REASONING_MODEL = _resolve_model(_REASONING_MODEL_STR)

# ─── App Configuration ───────────────────────────────────────────────────────
APP_NAME = "personal_assistant"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─── API Keys (set whichever provider you use) ───────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
SPORTS_API_KEY = os.getenv("SPORTS_API_KEY", "")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")

# ─── Session & Memory Configuration ──────────────────────────────────────────
SESSION_DB_URL = os.getenv("SESSION_DB_URL", "sqlite:///sessions.db")
MEMORY_SERVICE_TYPE = os.getenv("MEMORY_SERVICE", "in_memory")
SESSION_SERVICE_TYPE = os.getenv("SESSION_SERVICE", "auto")
ARTIFACT_SERVICE_TYPE = os.getenv("ARTIFACT_SERVICE", "in_memory")
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_AGENT_ENGINE_ID = os.getenv("VERTEX_AGENT_ENGINE_ID", "")
VERTEX_RAG_CORPUS_ID = os.getenv("VERTEX_RAG_CORPUS_ID", "")
ARTIFACT_GCS_BUCKET = os.getenv("ARTIFACT_GCS_BUCKET", "")
ARTIFACT_FILE_DIR = os.getenv("ARTIFACT_FILE_DIR", str(BASE_DIR / ".adk" / "artifacts"))

# ─── ADK Runtime Configuration ───────────────────────────────────────────────
ADK_ENABLE_RESUMABILITY = os.getenv("ADK_ENABLE_RESUMABILITY", "true")
ADK_ENABLE_CONTEXT_CACHE = os.getenv("ADK_ENABLE_CONTEXT_CACHE", "false")
ADK_ENABLE_EVENTS_COMPACTION = os.getenv("ADK_ENABLE_EVENTS_COMPACTION", "false")
ADK_CONTEXT_CACHE_INTERVALS = os.getenv("ADK_CONTEXT_CACHE_INTERVALS", "10")
ADK_CONTEXT_CACHE_TTL_SECONDS = os.getenv("ADK_CONTEXT_CACHE_TTL_SECONDS", "1800")
ADK_CONTEXT_CACHE_MIN_TOKENS = os.getenv("ADK_CONTEXT_CACHE_MIN_TOKENS", "0")
ADK_EVENT_COMPACTION_INTERVAL = os.getenv("ADK_EVENT_COMPACTION_INTERVAL", "40")
ADK_EVENT_COMPACTION_OVERLAP = os.getenv("ADK_EVENT_COMPACTION_OVERLAP", "6")
ADK_EVENT_COMPACTION_TOKEN_THRESHOLD = os.getenv("ADK_EVENT_COMPACTION_TOKEN_THRESHOLD", "")
ADK_EVENT_RETENTION_SIZE = os.getenv("ADK_EVENT_RETENTION_SIZE", "")
ADK_DEFAULT_STREAMING_MODE = os.getenv("ADK_DEFAULT_STREAMING_MODE", "none")
ADK_SAVE_INPUT_BLOBS = os.getenv("ADK_SAVE_INPUT_BLOBS", "false")
ADK_MAX_LLM_CALLS = os.getenv("ADK_MAX_LLM_CALLS", "500")

# ─── API Runtime Security Defaults ───────────────────────────────────────────
APP_API_KEY = os.getenv("APP_API_KEY", "")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "")
RATE_LIMIT_PER_MINUTE = os.getenv("RATE_LIMIT_PER_MINUTE", "60")


def _safe_int_env(name: str, default: int) -> int:
    """Parse an integer environment variable with a safe fallback."""
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a truthy/falsey environment variable."""
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


MAX_INPUT_CHARS = _safe_int_env("MAX_INPUT_CHARS", 8000)

# ─── Workspace Identity Files (OpenClaw-inspired) ────────────────────────────
def _load_workspace_file(filename: str) -> str:
    """Load a markdown file from the workspace directory."""
    filepath = WORKSPACE_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8").strip()
    return ""

SOUL_MD = _load_workspace_file("SOUL.md")
USER_MD = _load_workspace_file("USER.md")
AGENTS_MD = _load_workspace_file("AGENTS.md")
IDENTITY_MD = _load_workspace_file("IDENTITY.md")
TOOLS_MD = _load_workspace_file("TOOLS.md")

# ─── Parsed User Profile (backward compat) ───────────────────────────────────
USER_PROFILE = {
    "name": "Jithendra",
    "roles": ["Data Analyst", "Software Engineer"],
    "languages": ["Python", ".NET", "Node.js", "Terraform"],
    "interests": ["Data Analysis", "Software Engineering", "NFL", "Cricket", "Formula 1", "Streaming Technology", "Personal Finance"],
    "locations": {"primary": "Fort Wayne, IN", "secondary": ["Irving, TX", "Dallas, TX"]},
    "past_companies": ["Luxoft", "Pri-Med", "Tech Mahindra", "Capital One", "Ascension"],
    "education": ["George Washington University", "University of Oklahoma", "Purdue", "Emory"],
    "tech_stack": ["Apple ecosystem", "Linux", "GitHub", "AWS", "GCP", "Azure", "Surfshark VPN"],
    "nfl_team": "Dallas Cowboys",
    "f1_follows": ["Red Bull Racing", "McLaren"],
    "cricket_follows": ["India national team"],
}


def get_environment() -> str:
    """Return runtime environment mode."""
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_production() -> bool:
    """True when running in production mode."""
    return get_environment() == "production"


def get_session_db_url() -> str:
    """Session DB URL from runtime environment."""
    return os.getenv("SESSION_DB_URL", "sqlite:///sessions.db")


def get_cors_origins() -> list[str]:
    """
    Parse CORS origins from env.

    If unset, defaults to localhost origins for development ergonomics.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://localhost:3000", "http://localhost:8080"]


def auth_required() -> bool:
    """
    Whether inbound API auth is required.

    Defaults to True in production, False otherwise.
    Can be explicitly controlled with REQUIRE_AUTH=true/false.
    """
    explicit = os.getenv("REQUIRE_AUTH", "").strip().lower()
    if explicit:
        return explicit in {"1", "true", "yes", "on"}
    return is_production()


def get_api_auth_tokens() -> set[str]:
    """Parse one or more API tokens from APP_API_KEY (comma-separated)."""
    raw = os.getenv("APP_API_KEY", "").strip()
    if not raw:
        return set()
    return {token.strip() for token in raw.split(",") if token.strip()}


def get_rate_limit_per_minute() -> int:
    """Read and validate API rate limit per minute from env."""
    raw = os.getenv("RATE_LIMIT_PER_MINUTE", "60").strip()
    try:
        value = int(raw)
    except ValueError:
        return 60
    return value

# ─── Service Factories ────────────────────────────────────────────────────────
def create_session_service():
    """
    Create the appropriate ADK session service.

    Supported modes:
      - SESSION_SERVICE=auto (default): database in production/non-default DB URL, else in-memory
      - SESSION_SERVICE=database: force DatabaseSessionService
      - SESSION_SERVICE=in_memory: force InMemorySessionService
      - SESSION_SERVICE=vertex_ai: VertexAiSessionService (requires VERTEX_PROJECT + VERTEX_AGENT_ENGINE_ID)
    """
    session_service_type = os.getenv("SESSION_SERVICE", SESSION_SERVICE_TYPE).strip().lower()
    raw_session_db_url = get_session_db_url()

    if session_service_type == "vertex_ai":
        if VERTEX_PROJECT and VERTEX_AGENT_ENGINE_ID:
            from google.adk.sessions import VertexAiSessionService

            return VertexAiSessionService(
                project=VERTEX_PROJECT,
                location=VERTEX_LOCATION,
                agent_engine_id=VERTEX_AGENT_ENGINE_ID,
            )
        session_service_type = "auto"

    use_database = (
        session_service_type == "database"
        or (
            session_service_type == "auto"
            and (is_production() or raw_session_db_url != "sqlite:///sessions.db")
        )
    )

    if use_database:
        session_db_url = raw_session_db_url
        if session_db_url.startswith("sqlite:///"):
            # ADK's DatabaseSessionService expects an async driver URL.
            session_db_url = session_db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        from google.adk.sessions import DatabaseSessionService

        return DatabaseSessionService(db_url=session_db_url)

    from google.adk.sessions import InMemorySessionService

    return InMemorySessionService()


def create_memory_service():
    """
    Create the appropriate ADK memory service.

    Supported modes:
      - MEMORY_SERVICE=in_memory (default)
      - MEMORY_SERVICE=vertex_ai (VertexAiMemoryBankService)
      - MEMORY_SERVICE=vertex_rag (VertexAiRagMemoryService)
    """
    memory_service_type = os.getenv("MEMORY_SERVICE", MEMORY_SERVICE_TYPE)
    vertex_project = os.getenv("VERTEX_PROJECT", VERTEX_PROJECT)
    vertex_location = os.getenv("VERTEX_LOCATION", VERTEX_LOCATION)
    vertex_agent_engine_id = os.getenv("VERTEX_AGENT_ENGINE_ID", VERTEX_AGENT_ENGINE_ID)
    rag_corpus_id = os.getenv("VERTEX_RAG_CORPUS_ID", VERTEX_RAG_CORPUS_ID)

    if memory_service_type == "vertex_ai" and vertex_project and vertex_agent_engine_id:
        from google.adk.memory import VertexAiMemoryBankService
        return VertexAiMemoryBankService(
            project=vertex_project,
            location=vertex_location,
            agent_engine_id=vertex_agent_engine_id,
        )
    if memory_service_type == "vertex_rag" and rag_corpus_id:
        from google.adk.memory import VertexAiRagMemoryService

        top_k = _safe_int_env("VERTEX_RAG_TOP_K", 5)
        threshold_raw = os.getenv("VERTEX_RAG_DISTANCE_THRESHOLD", "10").strip()
        try:
            threshold = float(threshold_raw)
        except ValueError:
            threshold = 10.0
        return VertexAiRagMemoryService(
            rag_corpus=rag_corpus_id,
            similarity_top_k=top_k,
            vector_distance_threshold=threshold,
        )
    from google.adk.memory import InMemoryMemoryService
    return InMemoryMemoryService()


def create_artifact_service():
    """
    Create artifact service based on ARTIFACT_SERVICE / bucket/file settings.

    Supported modes:
      - ARTIFACT_SERVICE=in_memory (default)
      - ARTIFACT_SERVICE=file      (or ARTIFACT_FILE_DIR set)
      - ARTIFACT_SERVICE=gcs       (or ARTIFACT_GCS_BUCKET set)
    """
    artifact_service_type = os.getenv("ARTIFACT_SERVICE", ARTIFACT_SERVICE_TYPE).strip().lower()
    gcs_bucket = os.getenv("ARTIFACT_GCS_BUCKET", ARTIFACT_GCS_BUCKET).strip()
    artifact_file_dir_raw = os.getenv("ARTIFACT_FILE_DIR", "").strip()
    artifact_file_dir = artifact_file_dir_raw or ARTIFACT_FILE_DIR

    if artifact_service_type == "gcs" or gcs_bucket:
        if gcs_bucket:
            from google.adk.artifacts import GcsArtifactService

            return GcsArtifactService(bucket_name=gcs_bucket)
        artifact_service_type = "in_memory"

    if artifact_service_type == "file" or artifact_file_dir_raw:
        from google.adk.artifacts import FileArtifactService

        Path(artifact_file_dir).mkdir(parents=True, exist_ok=True)
        return FileArtifactService(root_dir=artifact_file_dir)

    from google.adk.artifacts import InMemoryArtifactService

    return InMemoryArtifactService()


def create_runtime_plugins():
    """Create ADK runtime plugins."""
    from personal_assistant.shared.adk_plugins import create_runtime_plugins as _create

    return _create()


def create_adk_app(root_agent):
    """
    Create an ADK App so app-level runtime features are active.
    """
    from google.adk.apps import App, ResumabilityConfig
    from google.adk.runners import ContextCacheConfig
    from google.adk.apps.app import EventsCompactionConfig

    from personal_assistant.shared.adk_plugins import create_runtime_plugins as _create

    context_cache_config = None
    if _env_bool("ADK_ENABLE_CONTEXT_CACHE"):
        context_cache_config = ContextCacheConfig(
            cache_intervals=_safe_int_env("ADK_CONTEXT_CACHE_INTERVALS", 10),
            ttl_seconds=_safe_int_env("ADK_CONTEXT_CACHE_TTL_SECONDS", 1800),
            min_tokens=_safe_int_env("ADK_CONTEXT_CACHE_MIN_TOKENS", 0),
        )

    events_compaction_config = None
    if _env_bool("ADK_ENABLE_EVENTS_COMPACTION"):
        token_threshold_raw = os.getenv("ADK_EVENT_COMPACTION_TOKEN_THRESHOLD", "").strip()
        retention_raw = os.getenv("ADK_EVENT_RETENTION_SIZE", "").strip()
        try:
            token_threshold = int(token_threshold_raw) if token_threshold_raw else None
        except ValueError:
            token_threshold = None
        try:
            retention_size = int(retention_raw) if retention_raw else None
        except ValueError:
            retention_size = None
        events_compaction_config = EventsCompactionConfig(
            compaction_interval=_safe_int_env("ADK_EVENT_COMPACTION_INTERVAL", 40),
            overlap_size=_safe_int_env("ADK_EVENT_COMPACTION_OVERLAP", 6),
            token_threshold=token_threshold,
            event_retention_size=retention_size,
        )

    resumability_config = ResumabilityConfig(
        is_resumable=_env_bool("ADK_ENABLE_RESUMABILITY", True)
    )

    return App(
        name=APP_NAME,
        root_agent=root_agent,
        plugins=_create(),
        context_cache_config=context_cache_config,
        events_compaction_config=events_compaction_config,
        resumability_config=resumability_config,
    )


def create_default_run_config():
    """
    Build a baseline RunConfig from env defaults.
    Returns None when defaults are effectively no-op.
    """
    from google.adk.agents.run_config import StreamingMode
    from google.adk.runners import RunConfig

    streaming_mode_raw = os.getenv("ADK_DEFAULT_STREAMING_MODE", "none").strip().lower()
    streaming_mode = {
        "none": StreamingMode.NONE,
        "sse": StreamingMode.SSE,
        "bidi": StreamingMode.BIDI,
    }.get(streaming_mode_raw, StreamingMode.NONE)

    save_input_blobs = _env_bool("ADK_SAVE_INPUT_BLOBS", False)
    max_llm_calls = _safe_int_env("ADK_MAX_LLM_CALLS", 500)

    if not save_input_blobs and streaming_mode == StreamingMode.NONE and max_llm_calls == 500:
        return None

    return RunConfig(
        save_input_blobs_as_artifacts=save_input_blobs,
        streaming_mode=streaming_mode,
        max_llm_calls=max_llm_calls,
    )


# ─── Validation ───────────────────────────────────────────────────────────────
def validate_config() -> dict:
    issues, warnings = [], []

    env = get_environment()
    session_db_url = get_session_db_url()
    cors_origins = get_cors_origins()
    rate_limit = get_rate_limit_per_minute()
    api_tokens = get_api_auth_tokens()
    memory_service_type = os.getenv("MEMORY_SERVICE", "in_memory").strip().lower()
    session_service_type = os.getenv("SESSION_SERVICE", "auto").strip().lower()
    artifact_service_type = os.getenv("ARTIFACT_SERVICE", "in_memory").strip().lower()
    artifact_gcs_bucket = os.getenv("ARTIFACT_GCS_BUCKET", "").strip()
    artifact_file_dir = os.getenv("ARTIFACT_FILE_DIR", ARTIFACT_FILE_DIR).strip()
    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    minimax_api_key = os.getenv("MINIMAX_API_KEY", "")
    serpapi_key = os.getenv("SERPAPI_KEY", "")
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY", "")
    sports_api_key = os.getenv("SPORTS_API_KEY", "")
    vertex_project = os.getenv("VERTEX_PROJECT", "").strip()
    vertex_engine_id = os.getenv("VERTEX_AGENT_ENGINE_ID", "").strip()
    rag_corpus_id = os.getenv("VERTEX_RAG_CORPUS_ID", "").strip()

    # Check that at least one LLM provider key is set
    has_any_llm_key = any([
        google_api_key,
        openai_api_key,
        anthropic_api_key,
        minimax_api_key,
        os.getenv("OLLAMA_API_BASE"),  # Ollama doesn't need a key, just a base URL
    ])
    
    if not has_any_llm_key:
        issues.append(
            "No LLM API key found. Set at least one of: "
            "GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, MINIMAX_API_KEY, "
            "or OLLAMA_API_BASE for local models."
        )
    
    # Model-specific validation
    model_str = os.getenv("DEFAULT_MODEL", _DEFAULT_MODEL_STR)
    if model_str.startswith('openai/') and not openai_api_key:
        issues.append(f"DEFAULT_MODEL is '{model_str}' but OPENAI_API_KEY is not set.")
    elif model_str.startswith('anthropic/') and not anthropic_api_key:
        issues.append(f"DEFAULT_MODEL is '{model_str}' but ANTHROPIC_API_KEY is not set.")
    elif model_str.startswith('minimax/') and not minimax_api_key:
        issues.append(f"DEFAULT_MODEL is '{model_str}' but MINIMAX_API_KEY is not set.")
    elif ('/' not in model_str or model_str.startswith('gemini')) and not google_api_key:
        issues.append(f"DEFAULT_MODEL is '{model_str}' but GOOGLE_API_KEY is not set.")
    
    # Check if LiteLLM is installed when using non-Gemini models
    if '/' in model_str and not model_str.startswith('gemini'):
        try:
            import litellm  # noqa: F401
        except ImportError:
            issues.append(
                f"DEFAULT_MODEL is '{model_str}' which requires LiteLLM. "
                "Install it with: pip install litellm"
            )

    # MiniMax Coding Plan key guidance (Anthropic-compatible API)
    if model_str.startswith("anthropic/MiniMax") and not anthropic_base_url:
        warnings.append(
            "Using anthropic/MiniMax model without ANTHROPIC_BASE_URL. "
            "Set ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic for MiniMax Anthropic-compatible API."
        )

    # Runtime API auth checks
    if auth_required() and not api_tokens:
        issues.append(
            "API authentication is required but APP_API_KEY is not set. "
            "Set APP_API_KEY or disable REQUIRE_AUTH for non-production usage."
        )

    # CORS hardening
    if "*" in cors_origins:
        if env == "production":
            issues.append("CORS_ORIGINS contains '*' in production. Use explicit trusted origins.")
        else:
            warnings.append("CORS_ORIGINS contains '*' — not recommended outside local development.")

    # Rate limiter sanity
    if rate_limit <= 0:
        warnings.append("RATE_LIMIT_PER_MINUTE <= 0 — rate limiting is effectively disabled.")

    # Session + memory production warnings
    if env == "production" and session_db_url == "sqlite:///sessions.db":
        warnings.append(
            "SESSION_DB_URL is default local SQLite in production. "
            "Use managed Postgres/Cloud SQL for multi-instance deployments."
        )
    if env == "production" and memory_service_type == "in_memory":
        warnings.append(
            "MEMORY_SERVICE=in_memory in production — long-term memory will not be shared across instances."
        )
    if env == "production" and artifact_service_type == "in_memory" and not artifact_gcs_bucket:
        warnings.append(
            "ARTIFACT_SERVICE=in_memory in production — generated artifacts are ephemeral."
        )

    # Runtime backend mode validation
    valid_session_modes = {"auto", "in_memory", "database", "vertex_ai"}
    if session_service_type not in valid_session_modes:
        issues.append(
            f"SESSION_SERVICE='{session_service_type}' is invalid. "
            "Use one of: auto, in_memory, database, vertex_ai."
        )
    if session_service_type == "vertex_ai" and (not vertex_project or not vertex_engine_id):
        warnings.append(
            "SESSION_SERVICE=vertex_ai requires VERTEX_PROJECT and VERTEX_AGENT_ENGINE_ID."
        )

    valid_memory_modes = {"in_memory", "vertex_ai", "vertex_rag"}
    if memory_service_type not in valid_memory_modes:
        issues.append(
            f"MEMORY_SERVICE='{memory_service_type}' is invalid. "
            "Use one of: in_memory, vertex_ai, vertex_rag."
        )
    if memory_service_type == "vertex_ai" and (not vertex_project or not vertex_engine_id):
        warnings.append(
            "MEMORY_SERVICE=vertex_ai requires VERTEX_PROJECT and VERTEX_AGENT_ENGINE_ID."
        )
    if memory_service_type == "vertex_rag" and not rag_corpus_id:
        warnings.append(
            "MEMORY_SERVICE=vertex_rag requires VERTEX_RAG_CORPUS_ID."
        )

    valid_artifact_modes = {"in_memory", "file", "gcs"}
    if artifact_service_type not in valid_artifact_modes:
        issues.append(
            f"ARTIFACT_SERVICE='{artifact_service_type}' is invalid. "
            "Use one of: in_memory, file, gcs."
        )
    if artifact_service_type == "gcs" and not artifact_gcs_bucket:
        warnings.append("ARTIFACT_SERVICE=gcs requires ARTIFACT_GCS_BUCKET.")
    if artifact_service_type == "file" and not artifact_file_dir:
        warnings.append("ARTIFACT_SERVICE=file requires ARTIFACT_FILE_DIR.")

    if not serpapi_key:
        warnings.append("SERPAPI_KEY not set — web_search tool will use mock data.")
    if not alpha_vantage_key:
        warnings.append("ALPHA_VANTAGE_KEY not set — finance tools will use mock data.")
    if not sports_api_key:
        warnings.append("SPORTS_API_KEY not set — sports tools will use mock data.")
    if not SOUL_MD:
        warnings.append("workspace/SOUL.md not found — using default persona.")
    if not USER_MD:
        warnings.append("workspace/USER.md not found — using default user profile.")
    return {"errors": issues, "warnings": warnings}
