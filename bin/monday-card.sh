#!/usr/bin/env bash
# monday-card.sh <decision.json>
# Creates a Monday.com item in the lane's group and posts the full routing
# decision as an item update. Read-only on money: it only records a task.
set -uo pipefail
ROOT="$HOME/Arvin"
DEC="${1:?usage: monday-card.sh <decision.json>}"
[ -s "$DEC" ] || { echo "no decision file: $DEC" >&2; exit 1; }

TOKENFILE="$HOME/secrets/monday.key"
[ -s "$TOKENFILE" ] || { echo "missing $TOKENFILE" >&2; exit 1; }
TOKEN="$(cat "$TOKENFILE")"
BOARD_ID="${MONDAY_BOARD_ID:?set MONDAY_BOARD_ID}"
GROUPS_MAP="$ROOT/config/monday-groups.json"   # { "<lane>": "<group_id>", ... }

# Milestone 1: out_of_scope decisions must produce NO Monday card and NO Gmail
# draft. scope_gate decided this email belongs to Gorgias / is unknown, so the
# pipeline stops here. We log the skip so the per-request stderr trace still
# shows that the email was seen and intentionally not carded.
action_check="$(jq -r '.action // ""' "$DEC")"
if [ "$action_check" = "out_of_scope" ]; then
  label="$(jq -r '.scope_label // "unknown"' "$DEC")"
  reason="$(jq -r '.reasoning // ""' "$DEC")"
  echo "[monday] out_of_scope ($label): no card created — $reason" >&2
  exit 0
fi

lane="$(jq -r '.primary_lane' "$DEC")"
summary="$(jq -r '.case_summary // .reasoning // "(no summary)"' "$DEC")"
sop="$(jq -r '.controlling_sop.id + " (" + .controlling_sop.status + ")"' "$DEC")"
action="$(jq -r '.action' "$DEC")"
approval="$(jq -r 'if .approval_required then "REQUIRED: " + .approver_role else "none" end' "$DEC")"
conf="$(jq -r '.confidence' "$DEC")"
conflict="$(jq -r 'if .sop_conflict.detected then "YES -> " + (.sop_conflict.archived_sop // "?") + "; " + (.sop_conflict.resolution // "") else "no" end' "$DEC")"
reason="$(jq -r '.reasoning' "$DEC")"
uncommitted="$(jq -r '(.draft.uncommitted_items // .uncommitted_items // []) | if length == 0 then "" else "\n\nUncommitted items (need human decision):\n" + (map("- " + .) | join("\n")) end' "$DEC")"
# Readable proposed-draft section — only when a customer-facing draft exists.
# Sits above the [DECISION JSON] block so the approver can read the reply
# without parsing JSON. Empty string for route/escalate cases with no draft.
draft_section="$(jq -r '
  if (.draft != null and (.draft.body // "") != "") then
    (
      "\n\n[PROPOSED DRAFT]\nTo:      " +
      ((.draft.to | if type == "object" then ((.value[0].address // .text // "") | tostring) else (. // "") end)) +
      "\nSubject: " + (.draft.subject // "") +
      "\n\n" + .draft.body
    )
  else "" end
' "$DEC")"
# Compact JSON form of the full decision — WF2 (Phase 1.5 approval-to-draft)
# parses this block out of the card update body to get draft.subject/body/to
# when the human flips Approval -> Approved on the card.
decision_json="$(jq -c . "$DEC")"

# resolve group id for the lane (fallback to MONDAY_GROUP_ID or "topics")
group_id="${MONDAY_GROUP_ID:-topics}"
if [ -s "$GROUPS_MAP" ]; then
  g="$(jq -r --arg l "$lane" '.[$l] // empty' "$GROUPS_MAP")"
  [ -n "$g" ] && group_id="$g"
fi

item_name="[$action] $summary"
note="Lane: $lane
SOP: $sop
SOP conflict: $conflict
Action: $action | Approval: $approval | Confidence: $conf
Reasoning: $reason${uncommitted}${draft_section}

[DECISION JSON]
${decision_json}"

api() { curl -s https://api.monday.com/v2 -H "Authorization: $TOKEN" \
        -H "Content-Type: application/json" -H "API-Version: 2024-10" \
        --data @-; }

# Pull the originating Gmail message_id out of the decision JSON. The bridge
# (triage-pipeline.sh) injects this into decision.email_metadata when an email
# went through n8n's Gmail Trigger. May be empty for ad-hoc replays / fixtures.
# Gmail message ids arrive as `<...@gmail.com>`; Monday's text column silently
# strips angle brackets, so we strip them ourselves before write+lookup so
# both sides match.
msg_id="$(jq -r '.email_metadata.messageId // ""' "$DEC" | tr -d '<>')"

# 0) idempotency check — Milestone 1 Rule 6: one Gmail email = one Monday item.
# If a card with this message_id already exists on the board, skip creating a
# new one and exit cleanly. Skipped when message_id is empty (no signal to
# match on) or when the column id is not configured.
if [ -n "$msg_id" ] && [ -n "${MONDAY_GMAIL_MSGID_COL_ID:-}" ]; then
  # Use ItemsPageByColumnValuesQuery — column_id is a single String, not array.
  dupe_query="$(jq -nc --arg b "$BOARD_ID" --arg c "$MONDAY_GMAIL_MSGID_COL_ID" --arg v "$msg_id" \
    '{query:"query($b:ID!,$c:String!,$v:String!){items_page_by_column_values(board_id:$b,columns:[{column_id:$c,column_values:[$v]}],limit:1){items{id name}}}",
      variables:{b:$b,c:$c,v:$v}}')"
  dupe_resp="$(printf '%s' "$dupe_query" | api)"
  existing_id="$(printf '%s' "$dupe_resp" | jq -r '.data.items_page_by_column_values.items[0].id // empty')"
  if [ -n "$existing_id" ]; then
    echo "[monday] idempotency: card $existing_id already exists for gmail message_id $msg_id — skipping create" >&2
    echo "[monday] reused item $existing_id in group '$group_id' | $item_name"
    exit 0
  fi
fi

# 1) create item
create_payload="$(jq -nc --arg b "$BOARD_ID" --arg g "$group_id" --arg n "$item_name" \
  '{query:"mutation($b:ID!,$g:String!,$n:String!){create_item(board_id:$b,group_id:$g,item_name:$n){id}}",
    variables:{b:$b,g:$g,n:$n}}')"
resp="$(printf '%s' "$create_payload" | api)"
item_id="$(printf '%s' "$resp" | jq -r '.data.create_item.id // empty')"
if [ -z "$item_id" ]; then
  echo "[monday] create_item FAILED: $resp" >&2; exit 1
fi

# 1b) stamp the originating Gmail message_id on the new card so future
# duplicates of the same email get caught by the idempotency check above.
if [ -n "$msg_id" ] && [ -n "${MONDAY_GMAIL_MSGID_COL_ID:-}" ]; then
  stamp_payload="$(jq -nc --arg b "$BOARD_ID" --arg i "$item_id" --arg c "$MONDAY_GMAIL_MSGID_COL_ID" --arg v "$msg_id" \
    '{query:"mutation($b:ID!,$i:ID!,$c:String!,$v:String!){change_simple_column_value(board_id:$b,item_id:$i,column_id:$c,value:$v){id}}",
      variables:{b:$b,i:$i,c:$c,v:$v}}')"
  printf '%s' "$stamp_payload" | api >/dev/null
fi

# 2) post the decision as an update
upd_payload="$(jq -nc --arg i "$item_id" --arg body "$note" \
  '{query:"mutation($i:ID!,$body:String!){create_update(item_id:$i,body:$body){id}}",
    variables:{i:$i,body:$body}}')"
printf '%s' "$upd_payload" | api >/dev/null

# 3) stamp Approval=Awaiting Review on the new card so WF2's webhook + the
# approver's queue view see it. Skip if the column id isn't configured.
if [ -n "${MONDAY_APPROVAL_COL_ID:-}" ]; then
  set_payload="$(jq -nc --arg b "$BOARD_ID" --arg i "$item_id" --arg c "$MONDAY_APPROVAL_COL_ID" \
    '{query:"mutation($b:ID!,$i:ID!,$c:String!){change_simple_column_value(board_id:$b,item_id:$i,column_id:$c,value:\"Awaiting Review\"){id}}",
      variables:{b:$b,i:$i,c:$c}}')"
  printf '%s' "$set_payload" | api >/dev/null
fi

echo "[monday] created item $item_id in group '$group_id' | $item_name"
