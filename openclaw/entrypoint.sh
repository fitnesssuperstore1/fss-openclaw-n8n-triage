#!/usr/bin/env bash
# OpenClaw container startup script (role model: coollabsio/openclaw scripts/).
#
# The skills folder is BIND-MOUNTED from the host directly into the workspace
# (see docker-compose.yml) — no copy step. Editing a SKILL.md on the host is
# live inside the container immediately.
#
# This script:
#   1. registers the OpenAI key from the env var into the agent auth-profile
#   2. starts the gateway in the foreground (container PID 1)
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
console.log('[entrypoint] openai auth profile registered');
"
fi

echo "[entrypoint] skills visible in workspace:"
ls /root/.openclaw/workspace/skills/ 2>/dev/null || echo "  (none mounted — check the ./skills bind in docker-compose.yml)"

echo "[entrypoint] starting gateway on :${OPENCLAW_GATEWAY_PORT:-18789}"
exec openclaw gateway run --force --port "${OPENCLAW_GATEWAY_PORT:-18789}"
