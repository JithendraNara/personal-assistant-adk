#!/bin/bash
jq '.projects["/Users/jithendranara/Documents/practice/github/personal-assistant-adk"].mcpServers["unified-memory"].env = {"UM_API_URL": "http://64.227.16.66:8000/api/v1", "UM_API_KEY": "um_master_bootstrap_key"}' ~/.claude.json > ~/.claude.json.tmp
mv ~/.claude.json.tmp ~/.claude.json
