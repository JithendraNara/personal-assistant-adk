#!/bin/bash
# Move mcpServers into a top-level .mcp key for Claude Code Compatibility
jq '{mcpServers: .mcpServers} as $mcp | . + $mcp' ~/.claude/settings.local.json > ~/.claude/settings.local.json.tmp
mv ~/.claude/settings.local.json.tmp ~/.claude/settings.local.json
