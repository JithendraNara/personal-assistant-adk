#!/bin/bash
jq '.mcpServers["unified-memory"].command = "/Users/jithendranara/Documents/practice/github/personal-assistant-adk/.venv/bin/python"' ~/.claude/settings.local.json > ~/.claude/settings.local.json.tmp
mv ~/.claude/settings.local.json.tmp ~/.claude/settings.local.json
