#!/usr/bin/env bash
# Start (or restart) the host-side services. n8n now runs in Docker with
# --restart unless-stopped, so the Docker daemon keeps it alive automatically;
# this script manages the two host-native services (gateway + triage bridge).
export PATH="$HOME/.npm-global/bin:$PATH"

# OpenClaw gateway (dashboard + agent) on 127.0.0.1:18789
if ! ss -tlnp 2>/dev/null | grep -q ':18789'; then
  setsid nohup openclaw gateway run --force > /tmp/openclaw-gateway.log 2>&1 < /dev/null &
  echo "openclaw gateway starting on :18789 ..."
else echo "openclaw gateway already up on :18789"; fi

# Triage HTTP bridge (n8n -> OpenClaw) on 127.0.0.1:8088
if ! ss -tlnp 2>/dev/null | grep -q ':8088'; then
  setsid nohup python3 "$HOME/Arvin/bin/triage-server.py" > /tmp/triage-bridge.log 2>&1 < /dev/null &
  echo "triage bridge starting on :8088 ..."
else echo "triage bridge already up on :8088"; fi

sleep 3
echo "--- host ports ---"; ss -tlnp 2>/dev/null | grep -E ':8088|:18789' || echo "(still starting)"
echo "--- n8n container (needs sudo to query) ---"
echo "  check with: sudo docker ps --filter name=n8n"
