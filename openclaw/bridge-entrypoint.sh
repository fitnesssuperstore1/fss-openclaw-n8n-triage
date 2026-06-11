#!/usr/bin/env bash
# Bridge container startup script.
#
# Runs triage-server.py (HTTP bridge on 127.0.0.1:8088). The chain it spawns
# calls `openclaw agent --local` per skill — that needs the openclaw CLI
# (in this image), the skills (bind-mounted into the workspace), and provider
# auth (registered below from the env var).
set -euo pipefail

if [ -n "${OPENAI_API_KEY:-}" ]; then
  AUTH_DIR="/root/.openclaw/agents/main/agent"
  mkdir -p "$AUTH_DIR"
  node -e "
const fs = require('fs');
const p = '$AUTH_DIR/auth-profiles.json';
let cfg = {version: 1, profiles: {}, usageStats: {}};
try { cfg = JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) {}
cfg.profiles = cfg.profiles || {};
cfg.profiles['openai:default'] = {type: 'api_key', provider: 'openai', key: process.env.OPENAI_API_KEY};
fs.writeFileSync(p, JSON.stringify(cfg, null, 2));
console.log('[bridge-entrypoint] openai auth profile registered');
"
fi

echo "[bridge-entrypoint] skills visible:"
ls /root/.openclaw/workspace/skills/ 2>/dev/null || echo "  (none mounted!)"

echo "[bridge-entrypoint] starting triage-server.py on :8088"
exec python3 /root/Arvin/bin/triage-server.py
