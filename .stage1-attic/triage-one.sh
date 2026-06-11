#!/usr/bin/env bash
# triage-one.sh <email.json>
# Calls the OpenClaw fitness-triage skill on one inbound email and prints the
# routing-decision JSON to stdout. Stderr carries diagnostics.
#
# If env var SOPS_FILE points at a JSON file containing the SOP catalog
# (e.g. fetched from Google Drive by n8n), its content is embedded directly
# into the OpenClaw prompt and used as the authoritative SOP source for this
# request. Otherwise the skill falls back to its on-disk index + files.
set -uo pipefail
export PATH="$HOME/.npm-global/bin:$PATH"
ROOT="$HOME/Arvin"

EMAIL_FILE="${1:?usage: triage-one.sh <email.json>}"
[ -s "$EMAIL_FILE" ] || { echo "no such email file: $EMAIL_FILE" >&2; exit 1; }

if [ -s "$HOME/secrets/openai.key" ]; then
  export OPENAI_API_KEY="$(cat "$HOME/secrets/openai.key")"
  MODEL="${OPENCLAW_MODEL:-openai/gpt-5.5}"
elif [ -s "$HOME/secrets/anthropic.key" ]; then
  export ANTHROPIC_API_KEY="$(cat "$HOME/secrets/anthropic.key")"
  MODEL="${OPENCLAW_MODEL:-anthropic/claude-sonnet-4-5}"
else
  echo "ERROR: need a key at ~/secrets/openai.key or ~/secrets/anthropic.key" >&2
  exit 1
fi
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
EMAIL_JSON="$(cat "$EMAIL_FILE")"

# If n8n passed Drive-sourced SOPs, embed them in the prompt and tell the agent
# to ignore /home/yoni/Arvin/sops/ for this run.
SOPS_BLOCK=""
if [ -n "${SOPS_FILE:-}" ] && [ -s "$SOPS_FILE" ]; then
  SOPS_JSON="$(cat "$SOPS_FILE")"
  SOPS_BLOCK="

SOP CATALOG (use these as the authoritative SOP source for THIS request; do NOT read /home/yoni/Arvin/sops/ off disk; each entry has a 'status' field — Active/Reference/Archived — and you must apply the skill's precedence rules to it):
${SOPS_JSON}"
fi

MSG="Run the fitness-triage skill on this single inbound email. Follow the skill exactly and respond with ONLY the routing-decision JSON object (no prose, no markdown code fences). INBOUND EMAIL JSON:
${EMAIL_JSON}${SOPS_BLOCK}"

SESSION_KEY="triage-$(basename "$EMAIL_FILE" .json)-$(date +%s%N)"
openclaw agent --local --json --agent main --session-key "$SESSION_KEY" \
  --model "$MODEL" --thinking low --timeout 180 \
  --message "$MSG" >"$WORK/envelope.json" 2>"$WORK/agent.err"
rc=$?
if [ $rc -ne 0 ]; then
  echo "openclaw agent failed (rc=$rc):" >&2
  cat "$WORK/agent.err" >&2
  exit $rc
fi

python3 "$ROOT/bin/extract_decision.py" "$WORK/envelope.json"
