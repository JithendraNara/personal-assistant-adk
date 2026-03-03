"""
Shared configuration — loads workspace identity files + environment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root
WORKSPACE_DIR = BASE_DIR / "workspace"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# ─── Model Configuration ─────────────────────────────────────────────────────
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")
REASONING_MODEL = os.getenv("REASONING_MODEL", "gemini-2.0-flash")

# ─── App Configuration ─────────────────────────────────────────────────────────
APP_NAME = "personal_assistant"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─── API Keys ─────────────────────────────────────────────────────────────────────GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
SPORTS_API_KEY = os.getenv("SPORTS_API_KEY", "")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "")

# ─── Session & Memory Configuration ──────────────────────────────────────────────
SESSION_DB_URL = os.getenv("SESSION_DB_URL", "sqlite:///sessions.db")
MEMORY_SERVICE_TYPE = os.getenv("MEMORY_SERVICE", "in_memory")
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_AGENT_ENGINE_ID = os.getenv("VERTEX_AGENT_ENGINE_ID", "")

# ─── Workspace Identity Files (OpenClaw-inspired) ────────────────────────────────────────
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

# ─── Parsed User Profile (backward compat) ───────────────────────────────────────────────
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

# ─── Service Factories ──────────────────────────────────────────────────────────────────
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

# ─── Validation ─────────────────────────────────────────────────────────────────────────────
def validate_config() -> dict:
    issues, warnings = [], []
    if not GOOGLE_API_KEY:
        issues.append("GOOGLE_API_KEY is required — agents will not function without it.")
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
