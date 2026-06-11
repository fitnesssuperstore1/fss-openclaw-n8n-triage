#!/usr/bin/env bash
# triage-pipeline.sh <email.json> [sops.json]
# End-to-end Phase-1 pipeline for ONE inbound email:
#   1) OpenClaw 4-skill chain (triage-chain.py) -> routing decision JSON
#   2) Create Gmail DRAFT (never sends) if a draft is warranted
#   3) Create Monday routing card with the decision
# If a second arg <sops.json> is passed, those SOPs (typically fetched by n8n
# from Google Drive) are embedded into the OpenClaw prompt by triage-chain.py
# instead of reading from ~/Arvin/sops/ on disk.
# Each step is best-effort and logged; Gmail/Monday steps skip cleanly if their
# secrets/IDs are not configured, so OpenClaw triage can be demoed alone.
set -uo pipefail
ROOT="$HOME/Arvin"
# Load config (model, Gmail user, Monday board id) and export to child scripts.
[ -f "$ROOT/config/env.sh" ] && set -a && source "$ROOT/config/env.sh" && set +a

EMAIL="${1:?usage: triage-pipeline.sh <email.json> [sops.json]}"
SOPS_FILE="${2:-}"
export SOPS_FILE  # triage-chain.py reads this

name="$(basename "$EMAIL" .json)"
OUT="$ROOT/out"; mkdir -p "$OUT"
DEC="$OUT/${name}.decision.json"

echo "############ TRIAGE: $name ############"
if [ -n "$SOPS_FILE" ] && [ -s "$SOPS_FILE" ]; then
  echo "(sops source: $SOPS_FILE — $(jq 'length' "$SOPS_FILE" 2>/dev/null || echo '?') entries)"
else
  echo "(sops source: ~/Arvin/sops/ on disk)"
fi

# 1) OpenClaw reasoning
if ! python3 "$ROOT/bin/triage-chain.py" "$EMAIL" "$SOPS_FILE" >"$DEC" 2>"$OUT/${name}.triage.err"; then
  echo "!! OpenClaw triage failed:"; cat "$OUT/${name}.triage.err"; exit 1
fi
echo "--- DECISION ---"; jq . "$DEC" 2>/dev/null || cat "$DEC"

# 1b) Inject email_metadata (threadId, messageId) into the decision JSON so the
# Monday card's [DECISION JSON] block carries it, and WF2 (Phase 1.5 approval-
# to-draft) can thread the Gmail draft onto the original customer conversation.
if [ -s "$EMAIL" ]; then
  tmpdec="$(mktemp)"
  if jq --slurpfile e "$EMAIL" '
    .email_metadata = {
      threadId:  ($e[0].threadId // ""),
      messageId: ($e[0].messageId // "")
    }
    | if (.email_metadata.threadId == "" and .email_metadata.messageId == "")
      then del(.email_metadata) else . end' "$DEC" > "$tmpdec" 2>/dev/null; then
    mv "$tmpdec" "$DEC"
  else
    rm -f "$tmpdec"
  fi
fi

# 2) Gmail draft step — handled by n8n now (Gmail Create Draft node after the bridge call).
#    Intentionally removed from the pipeline. Leaving a marker line in the log.
echo "--- GMAIL DRAFT --- handled downstream by n8n (Create Draft node)"

# 3) Monday card
echo "--- MONDAY CARD ---"
if [ -s "$HOME/secrets/monday.key" ] && [ -n "${MONDAY_BOARD_ID:-}" ]; then
  "$ROOT/bin/monday-card.sh" "$DEC" || echo "  (monday step error - see above)"
else
  echo "  skipped: set ~/secrets/monday.key and MONDAY_BOARD_ID to enable"
fi
echo "############ END $name ############"
echo
