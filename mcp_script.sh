#!/bin/bash
jq '.mcpServers += {"unified-memory": {"command": "python", "args": ["/Users/jithendranara/Documents/practice/github/personal-assistant-adk/mcp_server.py"]}}' ~/.claude/settings.local.json > ~/.claude/settings.local.json.tmp
mv ~/.claude/settings.local.json.tmp ~/.claude/settings.local.json
