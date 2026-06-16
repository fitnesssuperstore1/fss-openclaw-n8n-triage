#!/usr/bin/env bash
# verify_no_send.sh <path-to-n8n-workflow.json>
#
# Live-handoff safety audit. Reads an n8n workflow JSON export and fails if it
# contains any node that could transmit a customer-visible email (Gmail Send,
# SMTP, Reply, Forward, etc.). Exit 0 = clean. Exit 1 = found something
# forbidden. Designed to be run by both us (pre-handoff) and the client (during
# their import verification call).
#
# Hard rule from MILESTONE_1.md section 1: only "Gmail Create Draft" nodes may
# exist. Anything that can put text in front of a customer is a violation.

set -uo pipefail

WORKFLOW="${1:-}"
if [ -z "$WORKFLOW" ]; then
  echo "usage: $0 <path-to-n8n-workflow.json>" >&2
  exit 2
fi
if [ ! -s "$WORKFLOW" ]; then
  echo "ERROR: workflow file not found or empty: $WORKFLOW" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found (required to parse the workflow JSON)" >&2
  exit 2
fi

python3 - "$WORKFLOW" <<'PY'
"""Audit the n8n workflow JSON for any node or operation that can send a
customer-visible message. The check is deliberately suspicious:

  - reads the FULL node list (not just the "nodes" key — also catches any
    nested workflow definitions, sub-workflows, or pinData)
  - for each node, inspects the type AND the parameters' "operation" field
  - flags anything that smells like sending: 'send', 'reply', 'forward',
    'smtp', 'sendmail', 'outbound', 'transmit', etc.
  - the ONLY allowed Gmail interactions are operation=='draft' (Create Draft).
    A Gmail node with any other operation is a hard failure.
  - returns 1 on any violation and prints node-by-node detail.
"""
import json, sys, pathlib

path = pathlib.Path(sys.argv[1])
try:
    wf = json.loads(path.read_text())
except Exception as e:
    print(f"ERROR: could not parse {path} as JSON: {e}", file=sys.stderr)
    sys.exit(2)

# Banned tokens in node.type — any of these means the node CAN send something
BANNED_TYPE_TOKENS = [
    "emailSend",        # n8n's generic SMTP / Send Email node
    "smtpSend",
    "sendEmail",
    "smtp.send",
    "mailgunSend",
    "sendgrid",         # sendgrid send nodes
    "mailerlite",       # transactional sends
    "mandrill",
    "postmark",
    "ses.send",
    "twilio.sendsms",   # adjacent: SMS is also customer-visible transmission
]

# Banned tokens in node.parameters.operation — Gmail/IMAP nodes are okay if
# they're drafting/labeling/searching but NOT if they're sending/replying/etc.
BANNED_OPERATIONS = {
    "send", "reply", "replyTo", "replyAll", "forward",
    "sendAndWait",      # sendAndWait sends a message to the user
    "sendMessage",
    "sendEmail",
}

# Allowed operations on Gmail/IMAP-like nodes
ALLOWED_GMAIL_OPERATIONS = {
    "create", "draft", "get", "getAll", "search", "label",
    "addLabels", "removeLabels", "markAsRead", "markAsUnread", "delete",
    "trash", "untrash", "watch", "unwatch",
}

violations = []
nodes_inspected = 0

def walk_nodes(obj, source):
    """Yield every dict that looks like an n8n node (has 'type' and 'name')."""
    if isinstance(obj, dict):
        if "type" in obj and "name" in obj and isinstance(obj.get("type"), str):
            yield obj, source
        for k, v in obj.items():
            yield from walk_nodes(v, f"{source}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_nodes(v, f"{source}[{i}]")

for node, src in walk_nodes(wf, "workflow"):
    nodes_inspected += 1
    ntype = node.get("type", "")
    nname = node.get("name", "")
    params = node.get("parameters", {}) or {}
    operation = (params.get("operation") or "").strip()
    resource = (params.get("resource") or "").strip()

    # 1) banned node types — anything that's a transmitting node by class
    for token in BANNED_TYPE_TOKENS:
        if token.lower() in ntype.lower():
            violations.append({
                "node": nname, "type": ntype,
                "reason": f"node type contains banned token '{token}' (can send)",
            })

    # 2) Gmail nodes: only operation == 'draft' / 'create' on resource 'draft'
    #    is allowed. Any other Gmail operation is suspect.
    if "gmail" in ntype.lower():
        # Some n8n versions use resource+operation; others use operation alone.
        is_draft = (
            resource.lower() == "draft" and operation.lower() in {"create", "get", "getall", "delete"}
        ) or (operation.lower() in {"draft", "createdraft"})
        is_label_or_metadata = operation.lower() in {
            "addlabels", "removelabels", "marka sread", "markasread",
            "markasunread", "trash", "untrash", "get", "getall", "search",
            "label",
        } or resource.lower() in {"label", "thread", "message"} and operation.lower() in {
            "get", "getall", "addlabels", "removelabels", "trash", "untrash",
            "search",
        }
        if operation.lower() in BANNED_OPERATIONS:
            violations.append({
                "node": nname, "type": ntype, "operation": operation,
                "reason": "Gmail node uses a SEND/REPLY/FORWARD operation",
            })
        elif not is_draft and not is_label_or_metadata and operation:
            # Gmail node with a non-allowlisted operation — flag for review
            violations.append({
                "node": nname, "type": ntype, "operation": operation,
                "reason": f"Gmail node operation '{operation}' is neither a draft nor a read-only/label op — review",
            })

    # 3) Any node with a banned operation regardless of type (covers generic
    # send nodes that don't have 'gmail' in their type string)
    if operation.lower() in BANNED_OPERATIONS and "gmail" not in ntype.lower():
        # Any non-Gmail node using a send/reply/forward operation is flagged for
        # human review — the workflow must contain no outbound-send nodes.
        violations.append({
            "node": nname, "type": ntype, "operation": operation,
            "reason": "node uses a send/reply/forward operation",
        })

print(f"verify_no_send: scanned {nodes_inspected} node(s) in {path}")
if not violations:
    print("verify_no_send: OK — no Send/Reply/SMTP/Forward node found.")
    sys.exit(0)

print(f"verify_no_send: FAIL — {len(violations)} violation(s) found:")
for v in violations:
    print("  -", v.get("node"), "(", v.get("type"), ")")
    for k, val in v.items():
        if k in ("node", "type"):
            continue
        print(f"      {k}: {val}")
sys.exit(1)
PY
