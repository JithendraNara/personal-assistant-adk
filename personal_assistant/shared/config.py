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
#   Ollama (local):    ollama/llama3, ollama/mistral
#   Any LiteLLM model: https://docs.litellm.ai/docs/providers
#
# Set the corresponding API key in .env:
#   Gemini    → GOOGLE_API_KEY
#   OpenAI    → OPENAI_API_KEY
#   Anthropic → ANTHROPIC_API_KEY
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
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
SPORTS_API_KEY = os.getenv("SPORTS_API_KEY", "")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")

# ─── Session & Memory Configuration ──────────────────────────────────────────
SESSION_DB_URL = os.getenv("SESSION_DB_URL", "sqlite:///sessions.db")
MEMORY_SERVICE_TYPE = os.getenv("MEMORY_SERVICE", "in_memory")
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_AGENT_ENGINE_ID = os.getenv("VERTEX_AGENT_ENGINE_ID", "")

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

# ─── Service Factories ────────────────────────────────────────────────────────
def create_session_service():
    """Create the appropriate session service based on environment."""
    if ENVIRONMENT == "production" or SESSION_DB_URL != "sqlite:///sessions.db":
        from google.adk.sessions import DatabaseSessionService
        return DatabaseSessionService(db_url=SESSION_DB_URL)
    from google.adk.sessions import InMemorySessionService
    return InMemorySessionService()

def create_memory_service():
    """Create the appropriate memory service based on config."""
    if MEMORY_SERVICE_TYPE == "vertex_ai" and VERTEX_PROJECT and VERTEX_AGENT_ENGINE_ID:
        from google.adk.memory import VertexAiMemoryBankService
        return VertexAiMemoryBankService(
            project=VERTEX_PROJECT,
            location=VERTEX_LOCATION,
            agent_engine_id=VERTEX_AGENT_ENGINE_ID,
        )
    from google.adk.memory import InMemoryMemoryService
    return InMemoryMemoryService()

def create_artifact_service():
    """Create artifact service. GCS for production, in-memory for dev."""
    from google.adk.artifacts import InMemoryArtifactService
    return InMemoryArtifactService()

# ─── Validation ───────────────────────────────────────────────────────────────
def validate_config() -> dict:
    issues, warnings = [], []
    
    # Check that at least one LLM provider key is set
    has_any_llm_key = any([
        GOOGLE_API_KEY,
        OPENAI_API_KEY,
        ANTHROPIC_API_KEY,
        os.getenv("OLLAMA_API_BASE"),  # Ollama doesn't need a key, just a base URL
    ])
    
    if not has_any_llm_key:
        issues.append(
            "No LLM API key found. Set at least one of: "
            "GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "or OLLAMA_API_BASE for local models."
        )
    
    # Model-specific validation
    model_str = _DEFAULT_MODEL_STR
    if model_str.startswith('openai/') and not OPENAI_API_KEY:
        issues.append(f"DEFAULT_MODEL is '{model_str}' but OPENAI_API_KEY is not set.")
    elif model_str.startswith('anthropic/') and not ANTHROPIC_API_KEY:
        issues.append(f"DEFAULT_MODEL is '{model_str}' but ANTHROPIC_API_KEY is not set.")
    elif ('/' not in model_str or model_str.startswith('gemini')) and not GOOGLE_API_KEY:
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
    
    if not SERPAPI_KEY:
        warnings.append("SERPAPI_KEY not set — web_search tool will use mock data.")
    if not ALPHA_VANTAGE_KEY:
        warnings.append("ALPHA_VANTAGE_KEY not set — finance tools will use mock data.")
    if not SPORTS_API_KEY:
        warnings.append("SPORTS_API_KEY not set — sports tools will use mock data.")
    if not SOUL_MD:
        warnings.append("workspace/SOUL.md not found — using default persona.")
    if not USER_MD:
        warnings.append("workspace/USER.md not found — using default user profile.")
    return {"errors": issues, "warnings": warnings}
