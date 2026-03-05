"""
Security module — per-agent tool access policies and security audit.

Adapted from OpenClaw's per-agent sandbox and tool configuration.
See: src/agents/agent-scope.ts, src/node-host/exec-policy.ts

Patterns used:
  - Per-agent tool allow/deny lists (OpenClaw agents.list[].tools)
  - Security audit (OpenClaw `openclaw security audit`)
  - Input sanitization (OpenClaw channels.allowlists)
"""

import os
import re
import logging
import time
from collections import defaultdict, deque
from threading import Lock

logger = logging.getLogger(__name__)


# ─── Per-Agent Tool Policies (OpenClaw's tools.allow/deny pattern) ────────────

TOOL_POLICIES: dict[str, dict] = {
    # Research agent: only web-related tools
    "research_agent": {
        "allow": [
            "web_search", "fetch_webpage_summary", "get_news_headlines", "summarize_text",
            "google_search",
            "list_skills", "load_skill", "load_skill_resource",
        ],
    },
    # Data agent: only data analysis tools
    "data_agent": {
        "allow": [
            "profile_csv", "generate_sql_query", "analyze_dataframe_from_csv",
            "detect_anomalies", "generate_visualization_code",
            "list_skills", "load_skill", "load_skill_resource",
        ],
    },
    # Finance agent: deny tech tools
    "finance_agent": {
        "deny": ["analyze_code", "compare_technologies", "generate_tech_summary"],
    },
    # Scheduler agent: only scheduler tools
    "scheduler_agent": {
        "allow": [
            "create_task", "list_tasks", "update_task_status",
            "build_daily_plan", "set_reminder",
            "list_skills", "load_skill", "load_skill_resource",
        ],
    },
    # Sports agent: only sports tools
    "sports_agent": {
        "allow": [
            "get_nfl_scores", "get_f1_standings", "get_cricket_scores",
            "list_skills", "load_skill", "load_skill_resource",
        ],
    },
    # Career agent: only career tools
    "career_agent": {
        "allow": [
            "search_jobs", "analyze_skill_gaps", "generate_resume_suggestions",
            "compare_offers",
            "list_skills", "load_skill", "load_skill_resource",
        ],
    },
    # Tech agent: only tech tools
    "tech_agent": {
        "allow": [
            "analyze_code", "compare_technologies", "generate_tech_summary",
            "evaluate_architecture",
            "list_skills", "load_skill", "load_skill_resource",
        ],
    },
    # Workflow sub-agents
    "briefing_weather": {"allow": ["get_current_weather"]},
    "briefing_news": {"allow": ["get_news_headlines"]},
    "parallel_weather": {"allow": ["get_current_weather"]},
    "parallel_sports": {"allow": ["get_nfl_scores", "get_cricket_scores", "get_f1_standings"]},
    "parallel_finance": {"allow": ["get_stock_quote"]},
    # root_agent and any unlisted agents: full access (no policy = allow all)
}


def check_tool_access(agent_name: str, tool_name: str) -> tuple[bool, str]:
    """
    Check if an agent is allowed to use a specific tool.

    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    policy = TOOL_POLICIES.get(agent_name)

    if not policy:
        return True, "No policy defined — full access."

    allow_list = policy.get("allow")
    deny_list = policy.get("deny")

    if deny_list and tool_name in deny_list:
        return False, f"Tool '{tool_name}' is denied for agent '{agent_name}'."

    if allow_list and tool_name not in allow_list:
        return False, f"Tool '{tool_name}' is not in the allow list for agent '{agent_name}'."

    return True, "Access granted."


# ─── Input Sanitization ──────────────────────────────────────────────────────

# Patterns for detecting sensitive data (tuned for fewer false positives)
SENSITIVE_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN"),
    (re.compile(r"\b\d{16}\b"), "credit_card"),
    (re.compile(r"\b[A-Za-z0-9]{32,}\b(?=.*key)", re.IGNORECASE), "api_key"),
    (re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE), "password"),
]


def sanitize_input(text: str) -> tuple[str, list[str]]:
    """
    Check input for sensitive data patterns.

    Returns:
        Tuple of (sanitized_text, list of detected pattern names)
    """
    detected = []
    sanitized = text
    for pattern, name in SENSITIVE_PATTERNS:
        if pattern.search(text):
            detected.append(name)
            sanitized = pattern.sub(f"[REDACTED:{name}]", sanitized)
    return sanitized, detected


# ─── API Auth + Rate Limiting ────────────────────────────────────────────────

_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()


def parse_bearer_token(authorization_header: str | None) -> str | None:
    """Extract Bearer token from an Authorization header."""
    if not authorization_header:
        return None
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, value = parts[0].strip().lower(), parts[1].strip()
    if scheme != "bearer" or not value:
        return None
    return value


def resolve_api_key(
    x_api_key: str | None = None,
    authorization_header: str | None = None,
    query_api_key: str | None = None,
) -> str | None:
    """
    Resolve an API key from supported inputs.

    Priority:
      1. X-API-Key header
      2. Authorization: Bearer <token>
      3. Query param `api_key` (for websocket clients that cannot set headers)
    """
    if x_api_key:
        return x_api_key.strip()
    bearer = parse_bearer_token(authorization_header)
    if bearer:
        return bearer
    if query_api_key:
        return query_api_key.strip()
    return None


def is_auth_required() -> bool:
    """Return True when inbound auth should be enforced."""
    explicit = os.getenv("REQUIRE_AUTH", "").strip().lower()
    if explicit:
        return explicit in {"1", "true", "yes", "on"}
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


def expected_api_tokens() -> set[str]:
    """Return configured API tokens parsed from APP_API_KEY."""
    raw = os.getenv("APP_API_KEY", "").strip()
    if not raw:
        return set()
    return {token.strip() for token in raw.split(",") if token.strip()}


def check_api_key(api_key: str | None) -> tuple[bool, str]:
    """
    Validate inbound API key.

    Returns:
        Tuple of (allowed, reason)
    """
    if not is_auth_required():
        return True, "auth disabled"

    allowed_tokens = expected_api_tokens()
    if not allowed_tokens:
        return False, "auth is enabled but APP_API_KEY is not configured"

    if not api_key:
        return False, "missing api key"

    if api_key in allowed_tokens:
        return True, "ok"
    return False, "invalid api key"


def check_rate_limit(
    key: str,
    *,
    limit_per_minute: int | None = None,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """
    Sliding-window in-memory rate limiter.

    Returns:
        Tuple of (allowed, retry_after_seconds)
    """
    if not key:
        key = "anonymous"

    if limit_per_minute is None:
        raw = os.getenv("RATE_LIMIT_PER_MINUTE", "60").strip()
        try:
            limit_per_minute = int(raw)
        except ValueError:
            limit_per_minute = 60

    if limit_per_minute <= 0:
        return True, 0

    now = time.time()
    cutoff = now - window_seconds
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit_per_minute:
            retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
            return False, retry_after

        bucket.append(now)
        return True, 0


# ─── Security Audit (OpenClaw `openclaw security audit` equivalent) ──────────

def security_audit() -> dict:
    """
    Run a security audit on the current configuration.
    Checks API key exposure, CORS settings, session config, tool policies, and workspace files.

    Returns:
        A dict with 'status', 'checks', 'warnings', and 'recommendations'.
    """
    checks = []
    warnings = []
    recommendations = []

    # 1. API Key exposure
    sensitive_env_vars = [
        "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "SERPAPI_KEY", "NEWS_API_KEY", "ALPHA_VANTAGE_KEY",
    ]
    configured_keys = []
    for var in sensitive_env_vars:
        val = os.getenv(var, "")
        if val:
            configured_keys.append(var)
            # Check if key looks like a placeholder
            if val.startswith("your-") or val == "test" or len(val) < 10:
                warnings.append(f"⚠️  {var} looks like a placeholder, not a real key.")
    checks.append({
        "name": "API Keys",
        "status": "pass" if configured_keys else "info",
        "detail": f"{len(configured_keys)} API keys configured.",
    })

    # 2. CORS configuration
    cors_origins = os.getenv("CORS_ORIGINS", "")
    if not cors_origins:
        warnings.append("⚠️  CORS_ORIGINS not set — using localhost defaults.")
        recommendations.append("Set CORS_ORIGINS env var for production deployment.")
    elif "*" in cors_origins:
        warnings.append("🔴 CORS_ORIGINS contains '*' — allow all origins is a security risk.")
        recommendations.append("Restrict CORS_ORIGINS to specific trusted domains.")
    checks.append({
        "name": "CORS",
        "status": "fail" if "*" in cors_origins else "pass",
        "detail": cors_origins or "defaults to localhost",
    })

    # 3. Session persistence
    session_db_url = os.getenv("SESSION_DB_URL", "sqlite:///sessions.db")
    if session_db_url == "sqlite:///sessions.db":
        warnings.append("⚠️  Using default local SQLite sessions.")
        recommendations.append("Use managed Postgres/Cloud SQL for production scale.")
    checks.append({
        "name": "Session Backend",
        "status": "warning" if session_db_url == "sqlite:///sessions.db" else "pass",
        "detail": session_db_url,
    })

    # 4. API auth posture
    auth_enabled = is_auth_required()
    token_count = len(expected_api_tokens())
    if auth_enabled and token_count == 0:
        warnings.append("🔴 REQUIRE_AUTH enabled but APP_API_KEY is empty.")
        recommendations.append("Set APP_API_KEY (comma-separated tokens are supported).")
    checks.append({
        "name": "Inbound API Auth",
        "status": "fail" if auth_enabled and token_count == 0 else "pass",
        "detail": f"required={auth_enabled}, tokens={token_count}",
    })

    # 5. Tool policy coverage
    from personal_assistant.agents import (
        research_agent, data_agent, finance_agent, scheduler_agent,
        sports_agent, career_agent, tech_agent,
    )
    all_agents = [
        research_agent, data_agent, finance_agent, scheduler_agent,
        sports_agent, career_agent, tech_agent,
    ]
    covered = sum(1 for a in all_agents if a.name in TOOL_POLICIES)
    checks.append({
        "name": "Tool Policies",
        "status": "pass" if covered == len(all_agents) else "warning",
        "detail": f"{covered}/{len(all_agents)} agents have tool access policies.",
    })

    # 6. Workspace files
    workspace_files = ["workspace/SOUL.md", "workspace/USER.md", "workspace/AGENTS.md"]
    missing_files = [f for f in workspace_files if not os.path.exists(f)]
    if missing_files:
        warnings.append(f"⚠️  Missing workspace files: {', '.join(missing_files)}")
    checks.append({
        "name": "Workspace Identity",
        "status": "pass" if not missing_files else "warning",
        "detail": f"{len(workspace_files) - len(missing_files)}/{len(workspace_files)} files present.",
    })

    # Overall status
    has_failures = any(c["status"] == "fail" for c in checks)
    has_warnings = any(c["status"] == "warning" for c in checks)
    overall = "fail" if has_failures else ("warning" if has_warnings else "pass")

    return {
        "status": overall,
        "checks": checks,
        "warnings": warnings,
        "recommendations": recommendations,
    }
