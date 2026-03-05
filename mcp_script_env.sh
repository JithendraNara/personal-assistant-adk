#!/bin/bash
jq '.mcpServers["unified-memory"].env = {"UM_API_URL": "http://64.227.16.66:8000/api/v1", "UM_API_KEY": "um_master_bootstrap_key"}' ~/.claude/settings.local.json > ~/.claude/settings.local.json.tmp
mv ~/.claude/settings.local.json.tmp ~/.claude/settings.local.json
