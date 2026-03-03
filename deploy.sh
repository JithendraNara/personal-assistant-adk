#!/usr/bin/env bash
# deploy.sh — One-command deployment for Personal Assistant ADK
# Usage: curl -sSL https://raw.githubusercontent.com/JithendraNara/personal-assistant-adk/main/deploy.sh | bash
set -euo pipefail

echo "═══════════════════════════════════════════════════════════"
echo "  Personal Assistant ADK — Automated Deployment"
echo "═══════════════════════════════════════════════════════════"

# System packages
echo "[1/6] Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv git curl > /dev/null 2>&1
echo "  ✓ System packages installed"

# Clone repo
echo "[2/6] Cloning repository..."
cd /opt
if [ -d "personal-assistant-adk" ]; then
    cd personal-assistant-adk && git pull origin main
else
    git clone https://github.com/JithendraNara/personal-assistant-adk.git
    cd personal-assistant-adk
fi
echo "  ✓ Repository ready"

# Python venv
echo "[3/6] Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
echo "  ✓ Virtual environment created"

# Install dependencies
echo "[4/6] Installing Python dependencies (this takes 2-3 minutes)..."
pip install -e ".[all]" > /dev/null 2>&1
pip install litellm > /dev/null 2>&1
echo "  ✓ Dependencies installed"

# Ensure workspace and data dirs exist
mkdir -p workspace data/uploads

# Write .env if not exists
echo "[5/6] Configuring environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ⚠ Created .env from .env.example — edit it with your API key:"
    echo "    nano /opt/personal-assistant-adk/.env"
else
    echo "  ✓ .env already exists"
fi

# Test imports
echo "[6/6] Validating installation..."
source .venv/bin/activate
python3 -c "
from google.adk.agents import Context, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools import BaseTool, ToolContext, load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.artifacts import InMemoryArtifactService
print('  ✓ All ADK imports validated')
" 2>&1

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓ Deployment complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit .env:  nano /opt/personal-assistant-adk/.env"
echo "    2. Run CLI:    cd /opt/personal-assistant-adk && source .venv/bin/activate && python run.py"
echo "    3. Run API:    cd /opt/personal-assistant-adk && source .venv/bin/activate && python serve.py"
echo "    4. Health:     curl http://localhost:8080/health"
echo "═══════════════════════════════════════════════════════════"
