# Personal Assistant — Google ADK Multi-Agent

A production-grade personal AI assistant built on [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit), inspired by the OpenClaw multi-agent architecture. Routes user requests to specialized sub-agents, supports persistent sessions, long-term memory, and is deployable as a CLI, API server, Docker container, or Google Cloud service.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Workspace Identity System](#workspace-identity-system)
- [Callback Pipeline](#callback-pipeline)
- [Available Agents](#available-agents)
- [Workflow Agents](#workflow-agents)
- [API Server](#api-server)
- [Deployment](#deployment)
- [Configuration Reference](#configuration-reference)
- [ADK Skills](#adk-skills)
- [MCP Integration](#mcp-integration)
- [ADK Integrations](#adk-integrations)
- [Testing](#testing)

---

## Architecture Overview

```
root_agent  (LlmAgent — Coordinator)
│
├── research_agent       — Web search, news, summarization
├── data_agent           — CSV analysis, SQL generation, data profiling
├── career_agent         — Job search, skill gaps, salary benchmarks
├── finance_agent        — Budgeting, stocks, portfolio analysis
├── sports_agent         — NFL, Cricket, F1 scores & standings
├── scheduler_agent      — Tasks, reminders, daily planning
├── tech_agent           — Code review, tech comparisons, streaming setup
│
├── daily_briefing       ← SequentialAgent workflow
│   ├── briefing_weather
│   ├── briefing_tasks
│   ├── briefing_news
│   └── briefing_composer
│
└── info_gatherer        ← ParallelAgent workflow
    ├── parallel_weather
    ├── parallel_sports
    └── parallel_finance
```

**Key design principles:**

- **Single root coordinator**: All requests enter through `root_agent`, which uses ADK's built-in agent routing to select the right specialist.
- **Shared session state**: All agents read/write to the same session state, scoped by prefix (`user:`, `app:`, `temp:`).
- **OpenClaw-inspired callbacks**: A six-stage middleware pipeline (`before_agent`, `after_agent`, `before_model`, `after_model`, `before_tool`, `after_tool`) handles identity injection, guardrails, metrics, and memory archival.
- **ADK App runtime**: Runner is wired through `App(...)` to enable plugins, resumability, and optional context/runtime optimizations.
- **Workspace identity files**: Persona, user profile, and agent instructions are loaded from `workspace/*.md` files at session start, making them easy to edit without changing code.
- **Pluggable services**: Session, memory, and artifact services are swapped via environment variables — no code changes needed to go from in-memory dev to Vertex AI production.

### Project Layout

```
personal-assistant-adk/
├── personal_assistant/
│   ├── agent.py                  # Root coordinator + workflow agents
│   ├── agents/
│   │   ├── research_agent.py
│   │   ├── data_agent.py
│   │   ├── career_agent.py
│   │   ├── finance_agent.py
│   │   ├── sports_agent.py
│   │   ├── scheduler_agent.py
│   │   └── tech_agent.py
│   ├── shared/
│   │   ├── config.py             # Service factories, env vars, user profile
│   │   ├── callbacks.py          # Middleware pipeline
│   │   └── prompts.py            # Dynamic instruction providers
│   └── tools/
│       ├── web_tools.py
│       ├── data_tools.py
│       ├── career_tools.py
│       ├── finance_tools.py
│       ├── sports_tools.py
│       ├── scheduler_tools.py
│       └── tech_tools.py
├── workspace/
│   ├── SOUL.md                   # Persona, tone, boundaries
│   ├── USER.md                   # User profile (Jithendra)
│   ├── AGENTS.md                 # Agent routing instructions
│   ├── IDENTITY.md               # Combined identity context
│   └── TOOLS.md                  # Tool capability reference
├── data/
│   └── uploads/                  # User-uploaded files for data_agent
├── tests/
│   ├── test_config.py
│   ├── test_callbacks.py
│   └── test_agents.py
├── run.py                        # Interactive CLI runner
├── serve.py                      # FastAPI API server
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- At least one LLM provider key (Gemini, OpenAI, Anthropic, or MiniMax)

### 1. Install

```bash
git clone <repo-url>
cd personal-assistant-adk

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install package and dependencies
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
GOOGLE_API_KEY=your_key_here
```

For MiniMax Coding Plan via Anthropic-compatible API:

```env
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic
DEFAULT_MODEL=anthropic/MiniMax-M2.5
```

All other keys are optional — agents fall back to mock data when external APIs are not configured.

### 3. Run

**Interactive CLI (recommended for development):**

```bash
python run.py
```

**With SQLite session persistence (survives restarts):**

```bash
python run.py --persistent
```

**Resume a specific session:**

```bash
python run.py --session-id session_20260303_abc123
```

**Google ADK Dev UI (browser-based chat interface):**

```bash
adk web personal_assistant
```

**Simple ADK CLI:**

```bash
adk run personal_assistant
```

### 4. Talk to It

```
You: What's the latest on the Dallas Cowboys?
You: Run my daily briefing
You: Analyze the CSV I uploaded at data/uploads/sales.csv
You: Find data analyst jobs in Fort Wayne, IN
You: What's my budget looking like this month?
You: Review this Python function: def foo(x): return x*2
```

---

## Workspace Identity System

The assistant's persona and context are stored in plain Markdown files under `workspace/`. These are loaded once at session startup by the `before_agent_callback` and injected into session state. This means you can fully customize the assistant's behavior without touching Python code.

| File | Purpose |
|------|---------|
| `workspace/SOUL.md` | Persona definition — tone, style, ethical boundaries |
| `workspace/USER.md` | User profile — location, interests, tech stack, sports teams |
| `workspace/AGENTS.md` | Agent routing guidance — when to use which specialist |
| `workspace/IDENTITY.md` | Combined identity context (auto-generated or hand-crafted) |
| `workspace/TOOLS.md` | Reference for tool capabilities and usage patterns |

### How Identity Injection Works

1. On the first turn of a new session, `before_agent_callback` checks `state["_identity_loaded"]`.
2. If not loaded, it reads all five workspace files into `state["app:soul"]`, `state["app:user_profile"]`, etc.
3. The root agent's dynamic instruction provider (`root_instruction_provider`) reads these state keys and assembles the full system prompt for the LLM.
4. Sub-agents inherit session state, so they also have access to identity context.

### Customizing for a Different User

Edit `workspace/USER.md` to change the user profile. Edit `workspace/SOUL.md` to change the assistant's tone. No Python changes required.

---

## Callback Pipeline

The callback system is modeled after OpenClaw's middleware pattern, giving you fine-grained control at every stage of agent execution.

```
User Message
     │
     ▼
before_agent_callback    ← Identity injection, session rotation, turn logging
     │
     ▼
before_model_callback    ← Input guardrails, credential detection, prompt audit
     │
     ▼
  LLM Call
     │
     ▼
after_model_callback     ← Response sanitization, output quality logging
     │
     ▼
before_tool_callback     ← Argument validation, rate limiting, tool usage tracking
     │
     ▼
  Tool Execution
     │
     ▼
after_tool_callback      ← Result caching, error enrichment, tool result logging
     │
     ▼
after_agent_callback     ← Duration metrics, agent usage tracking, memory save trigger
     │
     ▼
Response to User
```

### Guardrails in `before_model_callback`

The pre-LLM callback scans user input for patterns that suggest credential exposure:

- `password: <value>` / `secret: <value>` / `token: <value>`
- `api_key: <value>` / `api-key: <value>`
- Long base64-like strings (possible embedded secrets)

When detected, the request is short-circuited and the user is warned. The LLM never sees the sensitive data.

### Auto-Memory Save

`after_agent_callback` sets `state["_memory_save_pending"] = True` every 5 interactions. The CLI runner (`run.py`) additionally calls `save_to_memory()` every 5 turns. This two-layer approach ensures context is preserved even across process restarts when using a persistent memory service.

---

## Available Agents

### `research_agent`
**Capabilities:** Web search, news retrieval, article summarization, fact-checking.

**Example prompts:**
- "Search for recent news about Formula 1 2026 season"
- "Summarize this article: [URL]"
- "What's the current state of AI regulation in the US?"

**Output key:** `research_last_topic`

---

### `data_agent`
**Capabilities:** CSV/Excel analysis, SQL query generation, data profiling, statistical summaries, chart descriptions.

Upload files to `data/uploads/` before asking the agent to analyze them.

**Example prompts:**
- "Profile the CSV at data/uploads/sales_q4.csv"
- "Write a SQL query to find the top 10 customers by revenue from this schema: ..."
- "What are the trends in this dataset?"

**Output key:** `data_last_analysis`

---

### `career_agent`
**Capabilities:** Job search (Indeed, LinkedIn style), skill gap analysis, salary benchmarks, resume tips, career path advice.

**Example prompts:**
- "Find data analyst jobs in Fort Wayne, IN with Python requirements"
- "What skills am I missing to become a Staff Engineer?"
- "What's the salary range for a Senior Data Analyst in Dallas, TX?"

**Output key:** `career_last_search`

---

### `finance_agent`
**Capabilities:** Personal budgeting, stock price lookups, portfolio analysis, market summaries, financial news.

> **Disclaimer:** The finance agent provides information and analysis only — not licensed financial advice. Always consult a qualified advisor before making investment decisions.

**Example prompts:**
- "What are the S&P 500 and NASDAQ doing today?"
- "Give me a simple budget breakdown for a $120k salary in Fort Wayne"
- "Any news on Apple stock this week?"

**Output key:** `finance_last_check`

---

### `sports_agent`
**Capabilities:** NFL scores and standings, Cricket match scores (India focus), Formula 1 standings and race results.

**Example prompts:**
- "How are the Dallas Cowboys doing this season?"
- "India vs Australia test match score"
- "F1 constructor standings — where are Red Bull and McLaren?"

**Output key:** `sports_last_update`

---

### `scheduler_agent`
**Capabilities:** Task management, reminders, daily planning, schedule summaries. Stores tasks in session state (`scheduler_tasks`, `scheduler_reminders`).

**Example prompts:**
- "Add a task: review pull request by Friday"
- "What do I have on my to-do list?"
- "Set a reminder: call dentist tomorrow at 10am"
- "Help me plan my day"

**Output key:** `scheduler_last_tasks`

---

### `tech_agent`
**Capabilities:** Code review, technical comparisons, architecture advice, streaming technology guidance, cloud platform help (AWS/GCP/Azure), developer tool recommendations.

**Example prompts:**
- "Review this Python function for performance issues: [code]"
- "Compare Kafka vs Pub/Sub for a real-time pipeline"
- "How do I set up a Plex + Jellyfin hybrid media server?"
- "Explain this Terraform error: [error message]"

**Output key:** `tech_last_query`

---

## Workflow Agents

Workflow agents are composite agents that coordinate multiple sub-agents to produce a structured output.

### `daily_briefing` — Sequential Workflow

Produces a personalized daily briefing by running four agents in sequence:

```
briefing_weather  →  briefing_tasks  →  briefing_news  →  briefing_composer
```

Each agent writes its output to session state. The final `briefing_composer` reads all three upstream outputs and composes a clean morning summary.

**Trigger phrases:** "morning briefing", "daily update", "what's my day look like", "run briefing"

**Example output:**
```
Good morning! Here's your briefing for Tuesday, March 3:

Weather: Fort Wayne, IN — 28°F, partly cloudy. No alerts.

Tasks due today:
• Review PR #42 (due today)
• Submit expense report (overdue)

Headlines:
• McLaren leads F1 2026 pre-season testing
• India wins 2nd Test vs England by 180 runs
• Apple announces M4 Pro Mac Pro
```

---

### `info_gatherer` — Parallel Workflow

Fetches weather, sports scores, and market data concurrently using ADK's `ParallelAgent`. All three sub-agents run simultaneously, reducing total latency.

```
parallel_weather  ┐
parallel_sports   ├── (concurrent) → merged session state
parallel_finance  ┘
```

**Trigger phrases:** "quick update", "what's happening", "give me a broad update"

Results are available in `state["gathered_weather"]`, `state["gathered_sports"]`, and `state["gathered_finance"]`.

---

## API Server

The FastAPI server (`serve.py`) exposes the assistant over HTTP — useful for integrations, webhooks, and production deployments.

### Start the Server

```bash
# Development (with auto-reload)
python serve.py

# Production
uvicorn serve:app --host 0.0.0.0 --port 8080 --workers 4
```

### Endpoints

#### `GET /mission-control`
Opens the custom mission-control dashboard with multiple pages:
- `/mission-control` (overview)
- `/mission-control/sessions`
- `/mission-control/agents`
- `/mission-control/console`

#### `GET /api/mission-control/snapshot`
Returns telemetry aggregates used by the dashboard:
- KPI overview (turns, active sessions, latency, error rate)
- Session grid
- Agent load board
- Recent turn/tool/error events
- Runtime metadata (services, model, plugins)

Requires API auth when `REQUIRE_AUTH=true`.

#### `GET /health`
Returns server status and service types.

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "session_service": "InMemorySessionService",
  "memory_service": "InMemoryMemoryService"
}
```

#### `POST /chat`
Send a message and get the agent's response.

**Request:**
```json
{
  "message": "What are the Dallas Cowboys standings?",
  "user_id": "jithendra",
  "session_id": "session_20260303_abc123"
}
```

If `session_id` is omitted, a new session is created automatically.

**Response:**
```json
{
  "response": "The Dallas Cowboys are currently...",
  "session_id": "session_20260303_abc123",
  "agents_involved": ["personal_assistant", "sports_agent"],
  "turn_duration_ms": 1842
}
```

#### `POST /sessions`
Explicitly create a new session with optional initial state.

**Request:**
```json
{
  "user_id": "jithendra",
  "initial_state": {
    "user:name": "Jithendra",
    "scheduler_tasks": []
  }
}
```

**Response:**
```json
{
  "session_id": "session_20260303_def456",
  "user_id": "jithendra",
  "created_at": "2026-03-03T10:00:00+00:00"
}
```

#### `POST /memory/save?user_id=jithendra&session_id=session_20260303_abc123`
Manually trigger a memory save for a session.

```json
{"status": "saved"}
```

### Interactive API Docs

When running in development mode, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

---

## Deployment

### Local Development

```bash
# CLI runner
python run.py

# API server
uvicorn serve:app --host 127.0.0.1 --reload --port 8080

# ADK Dev UI
adk web personal_assistant
```

### Docker

**Build:**
```bash
docker build -t personal-assistant .
```

**Run:**
```bash
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=your_key \
  -e ENVIRONMENT=production \
  -e APP_API_KEY=replace_with_long_random_token \
  personal-assistant
```

**Run with persistent sessions (mount SQLite):**
```bash
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=your_key \
  -e ENVIRONMENT=production \
  -e APP_API_KEY=replace_with_long_random_token \
  -e SESSION_DB_URL=sqlite:///data/sessions.db \
  -v $(pwd)/data:/app/data \
  personal-assistant
```

### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/personal-assistant

# Deploy
gcloud run deploy personal-assistant \
  --image gcr.io/YOUR_PROJECT/personal-assistant \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=your_key,ENVIRONMENT=production \
  --memory 1Gi \
  --timeout 300
```

Cloud Run automatically scales to zero when idle and scales out under load. Sessions are in-memory by default on Cloud Run (each instance has its own state). For shared session state across instances, set `SESSION_DB_URL` to a Cloud SQL or external PostgreSQL URL.

### Google Kubernetes Engine (GKE)

**Create a Kubernetes Secret for API keys:**

```bash
kubectl create secret generic personal-assistant-secrets \
  --from-literal=GOOGLE_API_KEY=your_key \
  --from-literal=SERPAPI_KEY=your_serpapi_key
```

**Deployment manifest (`k8s/deployment.yaml`):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: personal-assistant
spec:
  replicas: 2
  selector:
    matchLabels:
      app: personal-assistant
  template:
    metadata:
      labels:
        app: personal-assistant
    spec:
      containers:
      - name: personal-assistant
        image: gcr.io/YOUR_PROJECT/personal-assistant:latest
        ports:
        - containerPort: 8080
        envFrom:
        - secretRef:
            name: personal-assistant-secrets
        env:
        - name: ENVIRONMENT
          value: production
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: personal-assistant
spec:
  selector:
    app: personal-assistant
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

```bash
kubectl apply -f k8s/deployment.yaml
```

### Vertex AI Agent Engine (Managed)

When `MEMORY_SERVICE=vertex_ai` and Vertex credentials are set, the assistant uses Google's managed Agent Engine for persistent, scalable memory that works across deployments.

```env
MEMORY_SERVICE=vertex_ai
VERTEX_PROJECT=your-gcp-project
VERTEX_LOCATION=us-central1
VERTEX_AGENT_ENGINE_ID=your-engine-id
```

---

## Configuration Reference

All configuration is via environment variables. Copy `.env.example` to `.env` to get started.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | No* | — | Gemini API key from Google AI Studio or GCP |
| `OPENAI_API_KEY` | No* | — | OpenAI API key (used when `DEFAULT_MODEL` starts with `openai/`). |
| `ANTHROPIC_API_KEY` | No* | — | Anthropic API key (also used for Anthropic-compatible providers like MiniMax Coding Plan). |
| `MINIMAX_API_KEY` | No* | — | MiniMax native API key (used when `DEFAULT_MODEL` starts with `minimax/`). |
| `SERPAPI_KEY` | No | — | SerpAPI key for live web search. Falls back to mock data. |
| `ALPHA_VANTAGE_KEY` | No | — | Alpha Vantage key for live stock prices. Falls back to mock data. |
| `SPORTS_API_KEY` | No | — | Sports API key for live scores. Falls back to mock data. |
| `OPENWEATHER_KEY` | No | — | OpenWeatherMap key for live weather. Falls back to mock data. |
| `SESSION_DB_URL` | No | `sqlite:///sessions.db` | SQLAlchemy URL for session persistence. Use PostgreSQL URL for production. |
| `MEMORY_SERVICE` | No | `in_memory` | `in_memory` or `vertex_ai` |
| `VERTEX_PROJECT` | No* | — | GCP project ID. Required when `MEMORY_SERVICE=vertex_ai`. |
| `VERTEX_LOCATION` | No | `us-central1` | Vertex AI region. |
| `VERTEX_AGENT_ENGINE_ID` | No* | — | Agent Engine ID. Required when `MEMORY_SERVICE=vertex_ai`. |
| `DEFAULT_MODEL` | No | `gemini-2.0-flash` | Gemini model for all agents. |
| `REASONING_MODEL` | No | `gemini-2.0-flash` | Model for complex reasoning tasks. |
| `ANTHROPIC_BASE_URL` | No | — | Optional Anthropic-compatible endpoint (for example MiniMax: `https://api.minimax.io/anthropic`). |
| `ENVIRONMENT` | No | `development` | `development` or `production`. Production enables SQLite session persistence. |
| `APP_API_KEY` | No* | — | Inbound API auth token(s), comma-separated. Required when auth is enabled. |
| `REQUIRE_AUTH` | No | auto (`true` in production) | Force inbound auth on/off: `true` or `false`. |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | Per-key/IP inbound request limit (sliding window). |
| `MAX_INPUT_CHARS` | No | `8000` | Max accepted inbound message length. |
| `CORS_ORIGINS` | No | localhost defaults | Comma-separated allowed browser origins. |
| `LOG_LEVEL` | No | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `HOST` | No | `127.0.0.1` | API bind host. Set `0.0.0.0` when exposing behind a container/LB. |
| `PORT` | No | `8080` | Port for the FastAPI server. |

### ADK Runtime + Backend Extensions

| Variable | Purpose |
|----------|---------|
| `SESSION_SERVICE` | `auto`, `in_memory`, `database`, or `vertex_ai` |
| `ARTIFACT_SERVICE` | `in_memory`, `file`, or `gcs` |
| `ARTIFACT_GCS_BUCKET` | GCS bucket when `ARTIFACT_SERVICE=gcs` |
| `ARTIFACT_FILE_DIR` | Filesystem path when `ARTIFACT_SERVICE=file` |
| `VERTEX_RAG_CORPUS_ID` | Corpus ID when `MEMORY_SERVICE=vertex_rag` |
| `ADK_ENABLE_RESUMABILITY` | Enable App-level resumability |
| `ADK_ENABLE_CONTEXT_CACHE` | Enable context caching |
| `ADK_ENABLE_EVENTS_COMPACTION` | Enable events compaction |
| `ADK_DEFAULT_STREAMING_MODE` | `none`, `sse`, or `bidi` |
| `ADK_SAVE_INPUT_BLOBS` | Persist input blobs as artifacts |
| `ADK_MAX_LLM_CALLS` | Per-run model call cap |

### Service Selection Logic

**Session service:**
- `ENVIRONMENT=production` or `SESSION_DB_URL` is non-default → `DatabaseSessionService` (SQLite or Postgres)
- Otherwise → `InMemorySessionService`

**Memory service:**
- `MEMORY_SERVICE=vertex_ai` + `VERTEX_PROJECT` + `VERTEX_AGENT_ENGINE_ID` are all set → `VertexAiMemoryBankService`
- `MEMORY_SERVICE=vertex_rag` + `VERTEX_RAG_CORPUS_ID` are set → `VertexAiRagMemoryService`
- Otherwise → `InMemoryMemoryService`

**Artifact service:**
- `ARTIFACT_SERVICE=gcs` + `ARTIFACT_GCS_BUCKET` set → `GcsArtifactService`
- `ARTIFACT_SERVICE=file` (or `ARTIFACT_FILE_DIR` set) → `FileArtifactService`
- Otherwise → `InMemoryArtifactService`

**CLI `--persistent` flag:**
Sets `ENVIRONMENT=production` at runtime, switching to `DatabaseSessionService` without requiring `.env` changes.

**Inbound API auth + limits:**
- Auth is automatically required in production unless overridden with `REQUIRE_AUTH=false`.
- Supply token(s) in `APP_API_KEY`, then call API with `X-API-Key` or `Authorization: Bearer <token>`.
- WebSocket supports `X-API-Key` header or `?api_key=<token>`.
- Rate limiting is enforced via `RATE_LIMIT_PER_MINUTE`.

`*` At least one provider path must be configured:
- Gemini: `GOOGLE_API_KEY` + Gemini model name.
- OpenAI: `OPENAI_API_KEY` + `DEFAULT_MODEL=openai/...`.
- Anthropic: `ANTHROPIC_API_KEY` + `DEFAULT_MODEL=anthropic/...`.
- MiniMax native: `MINIMAX_API_KEY` + `DEFAULT_MODEL=minimax/...`.
- MiniMax Anthropic-compatible: `ANTHROPIC_API_KEY` + `ANTHROPIC_BASE_URL` + `DEFAULT_MODEL=anthropic/MiniMax-M2.5`.

**MiniMax Coding Plan API (Anthropic-compatible):**
- Set `ANTHROPIC_API_KEY` to your Coding Plan key.
- Set `ANTHROPIC_BASE_URL=https://api.minimax.io/anthropic`.
- Use `DEFAULT_MODEL=anthropic/MiniMax-M2.5`.

---

## ADK Skills

This project now uses ADK-native skills (`google.adk.skills` + `SkillToolset`) from `workspace/skills/*`.

Rules:
- Each skill directory name must match `name:` in its `SKILL.md` frontmatter.
- `agent:` in frontmatter scopes a skill to a specific agent.
- Skills are exposed through native ADK tools: `list_skills`, `load_skill`, `load_skill_resource`.

Current skills:
- `workspace/skills/web-research`
- `workspace/skills/daily-standup`
- `workspace/skills/interview-prep`

---

## MCP Integration

The assistant can connect to Model Context Protocol (MCP) servers to extend its tool set. MCP enables the assistant to interface with external services (databases, file systems, REST APIs, etc.) through a standardized protocol.

### Runtime Wiring (Built In)

This project now supports optional ADK toolsets at runtime (wired into `root_agent`):
- `MCPToolset` via `MCP_SERVER_*` environment variables
- `OpenAPIToolset` via `OPENAPI_SPEC_*` environment variables

If unset, the assistant runs normally with built-in tools only.

### MCP Environment Variables

- `MCP_SERVER_COMMAND` (example: `npx`)
- `MCP_SERVER_ARGS` (JSON array or shell-style string)
- `MCP_SERVER_CWD` (optional)
- `MCP_SERVER_ENV_JSON` (optional JSON object)
- `MCP_AGENTS` (comma-separated list or `*`; defaults to core agents)

Example:

```bash
export MCP_SERVER_COMMAND="npx"
export MCP_SERVER_ARGS='["-y","@modelcontextprotocol/server-filesystem","/tmp"]'
```

### OpenAPI Environment Variables

- `OPENAPI_SPEC_PATH` (local JSON/YAML file)
- `OPENAPI_SPEC_URL` (remote JSON/YAML URL)
- `OPENAPI_SPEC_JSON` (inline JSON string)
- `OPENAPI_SPEC_TYPE` (`json` or `yaml`)
- `OPENAPI_TOOL_NAME_PREFIX` (optional)
- `OPENAPI_AGENTS` (comma-separated list or `*`)

---

## ADK Integrations

This repo supports ADK integrations in three ways:

1. **Built-in integration tools**
- Enable Google Search tool:
  - `ENABLE_GOOGLE_SEARCH_TOOL=true`
  - `GOOGLE_SEARCH_AGENTS=research_agent,personal_assistant`

2. **Toolset integrations**
- `MCPToolset` via `MCP_SERVER_*` env vars
- `OpenAPIToolset` via `OPENAPI_SPEC_*` env vars

3. **External plugin integrations**
- Load plugin classes/instances via import path:
  - `ADK_INTEGRATION_PLUGINS=package.module:PluginClass,other.module:plugin_instance`

---

## Testing

### Run Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=personal_assistant --cov-report=html

# Run a specific test file
pytest tests/test_agents.py -v

# Run tests matching a keyword
pytest -k "test_callbacks" -v

# Security + dependency audits
bandit -q -r personal_assistant serve.py run.py mcp_server.py
pip-audit --local
pip check
```

### CI

GitHub Actions workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

CI runs on every push/PR:
- `ruff check .`
- `pytest -q`
- `pip check`
- `pip-audit --local`
- `bandit` security scan

### Test Structure

| File | What It Tests |
|------|--------------|
| `tests/test_config.py` | `APP_NAME`, `USER_PROFILE`, workspace file loading, `validate_config()` |
| `tests/test_callbacks.py` | All five callback functions — identity injection, guardrails, metrics |
| `tests/test_agents.py` | Agent existence, sub-agent wiring, callback attachment, workflow types |

### Writing New Tests

Tests use `pytest-asyncio` for async test support. The `pyproject.toml` sets `asyncio_mode = "auto"`, so you don't need `@pytest.mark.asyncio` decorators.

```python
# Example: test a new agent
async def test_my_new_agent():
    from personal_assistant.agents.my_agent import my_agent
    assert my_agent.name == "my_agent"
    assert my_agent.output_key == "my_agent_result"
```

### Mocking External Services

For unit tests that would normally call Gemini or external APIs, use `unittest.mock`:

```python
from unittest.mock import AsyncMock, patch

async def test_chat_endpoint():
    with patch("serve.runner") as mock_runner:
        mock_runner.run_async.return_value = async_iter([mock_event])
        # ... test the endpoint
```

---

## Contributing

1. Follow the existing module structure — add new agents under `personal_assistant/agents/`, tools under `personal_assistant/tools/`.
2. Every new agent should have an `output_key` for state storage.
3. Register new specialist agents in `root_agent.sub_agents` in `agent.py`.
4. Update `workspace/AGENTS.md` to tell the coordinator when to route to your new agent.
5. Add tests in `tests/test_agents.py`.

---

## License

MIT
