#!/bin/bash
jq '.permissions.allow += ["mcp__unified-memory__um_search_memory", "mcp__unified-memory__um_add_memory", "mcp__unified-memory__um_get_profile"] | .permissions.allow |= unique' ~/.claude/settings.local.json > ~/.claude/settings.local.json.tmp
mv ~/.claude/settings.local.json.tmp ~/.claude/settings.local.json
