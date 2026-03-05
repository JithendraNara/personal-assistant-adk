#!/usr/bin/env python3
"""
Universal Auto-Connector for UnifiedMemory.

This script scans your computer for all supported AI development clients
and automatically injects the UnifiedMemory MCP (Model Context Protocol) 
configuration into them.

Supported Clients:
- Claude Desktop
- Cursor
- VS Code (via Cline / Roo Cline)
- Claude Code (CLI)
"""

import os
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")

def get_mcp_config():
    """Generates the MCP configuration block to be injected."""
    # Getting the absolute path to the local mcp_server.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    python_bin = os.path.join(current_dir, ".venv", "bin", "python")
    # Fallback to system python if venv doesn't exist
    if not os.path.exists(python_bin):
        python_bin = "python3"
        
    mcp_server_path = os.path.join(current_dir, "mcp_server.py")
    
    return {
        "command": python_bin,
        "args": [mcp_server_path],
        "env": {
            "UM_API_URL": "http://64.227.16.66:8000/api/v1",
            "UM_API_KEY": "um_master_bootstrap_key"
        }
    }

def update_json_file(file_path: Path, config_path: list, new_server_config: dict):
    """Safely updates a deeply nested JSON file."""
    if not file_path.exists():
        # Create empty base structure if file doesn't exist but parent dir does
        if not file_path.parent.exists():
            return False
            
        logging.info(f"Creating new config file: {file_path}")
        data = {}
        with open(file_path, 'w') as f:
            json.dump(data, f)
    else:
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                data = json.loads(content) if content else {}
        except Exception as e:
            logging.error(f"Failed to parse {file_path}: {e}")
            return False

    current = data
    for key in config_path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
        
    target_key = config_path[-1]
    
    # Check if exactly the same to avoid unnecessary writes
    if target_key in current and current[target_key] == new_server_config:
        logging.info(f"✅ Already connected: {file_path.name}")
        return True
        
    current[target_key] = new_server_config

    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logging.info(f"🚀 Successfully connected: {file_path.name}")
        return True
    except Exception as e:
        logging.error(f"Failed to write {file_path}: {e}")
        return False

def connect_cursor(config: dict):
    # Cursor stores MCP settings per-workspace in `.cursor/mcp.json` or globally.
    # We will inject it into the user's home global cursor settings if possible, or print instructions.
    paths = [
        Path.home() / ".cursor" / "mcp.json",
        Path.cwd() / ".cursor" / "mcp.json"
    ]
    for path in paths:
        if path.parent.exists():
            update_json_file(path, ["mcpServers", "unified-memory"], config)

def connect_claude_desktop(config: dict):
    path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    update_json_file(path, ["mcpServers", "unified-memory"], config)

def connect_vscode_cline(config: dict):
    # Cline extension for VS Code
    path = Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
    update_json_file(path, ["mcpServers", "unified-memory"], config)

def connect_vscode_roo_cline(config: dict):
    # Roo Cline extension
    path = Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json"
    update_json_file(path, ["mcpServers", "unified-memory"], config)

def connect_claude_code(config: dict, workspace_path: str = None):
    # Claude Code stores project-specific configs in ~/.claude.json under "projects"
    path = Path.home() / ".claude.json"
    if not workspace_path:
        workspace_path = str(Path.cwd())
        
    update_json_file(path, ["projects", workspace_path, "mcpServers", "unified-memory"], config)

def main():
    print("="*60)
    print("🧠 UnifiedMemory Universal Auto-Connector")
    print("="*60)
    print("Scanning system for AI clients...\n")
    
    cfg = get_mcp_config()
    
    # Execute integrations
    connect_claude_desktop(cfg)
    connect_cursor(cfg)
    connect_vscode_cline(cfg)
    connect_vscode_roo_cline(cfg)
    connect_claude_code(cfg, "/Users/jithendranara")
    connect_claude_code(cfg, "/Users/jithendranara/Documents/practice/github/personal-assistant-adk")
    connect_claude_code(cfg, "/Users/jithendranara/Documents/practice/github/unified-memory")

    print("\n" + "="*60)
    print("Done! All detected AI clients are now connected to UnifiedMemory.")
    print("Note: You may need to restart your editors (VS Code, Cursor, Claude Desktop) for the new MCP server to initialize.")
    print("="*60)

if __name__ == "__main__":
    main()
