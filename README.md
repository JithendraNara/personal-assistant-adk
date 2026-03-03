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
- [MCP Integration](#mcp-integration)
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

See full documentation below.

## License

MIT
