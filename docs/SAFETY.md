# Safety

This doc walks through the six hard rules from `MILESTONE_1.md` §1 and shows
exactly how each one is enforced — and how anyone (us, the client, an
auditor) can verify it.

The shared principle: **safety is a property of the wiring, not of the AI's
behaviour on any given run.** Even a worst-case AI hallucination cannot
produce a customer-visible side effect, because the structures that would be
required to do so simply don't exist in the workflow.

---

## The four-layer enforcement model

Every hard safety rule is enforced in at least **two of three layers**, so no
single point of failure can violate it.

1. **Skill prompt** — hard rules embedded in the `.md` file the AI sees. Easy
   to inspect; the AI is told the rule in plain English.
2. **JSON Schema validation** — `triage-chain.py` runs each skill output
   through `Draft7Validator` against `schemas/<skill>.json` immediately after
   the call. Failure stops the chain and escalates. Easy to audit; you can
   grep the schema for the constraint.
3. **n8n workflow structure** — the workflow graph itself does not contain
   nodes that could violate the rule. Easy to verify by reading the exported
   JSON.

For some rules a fourth layer applies:

4. **`audit_check` independent reviewer** — the final skill in the chain
   re-reads everything upstream and force-escalates if anything is
   inconsistent or any no-promise rule is violated in the draft body. This
   is "even if the structure and schemas pass, this last skill checks for
   sloppy semantic violations."

---

## Rule 1 — No Gmail Send / Reply / SMTP node anywhere

**Where it's enforced:** n8n workflow structure (Layer 3).

**The proof:** the only Gmail node anywhere in the exported workflow JSON is
`Gmail Create Draft`. There is no Send, no Reply, no Forward, no SMTP, no
Mailgun, no SES, no SendGrid. Any of those would be a deal-breaker.

**How to verify yourself:**

```bash
bash scripts/verify_no_send.sh n8n/fitness-triage.workflow.json
```

The script greps the workflow JSON for any node whose `type` or `operation`
suggests a transmitting capability:

- Banned node types (any of these = exit 1): `emailSend`, `smtpSend`,
  `sendEmail`, `sendgrid`, `mailgunSend`, `mandrill`, `postmark`, `ses.send`,
  `twilio.sendsms`.
- Banned operations on any node: `send`, `reply`, `replyTo`, `replyAll`,
  `forward`, `sendEmail`.
- Gmail node operations restricted to: `draft` / `create` (create draft),
  plus read-only ops (`get`, `getAll`, `search`, `label`, etc.).

Exit 0 = clean, exit 1 = found something forbidden (with the node names
listed).

The script ships in `scripts/verify_no_send.sh` and is intended to run both
pre-handoff and during the client's live verification call.

---

## Rule 2 — Gmail Create Draft only

Same enforcement as Rule 1. Verified by the same script.

The Gmail Create Draft node is configured to:

- `resource: "draft"`
- `operation: "create"` (or `"draft"` depending on n8n version)
- `threadId: {{ $('Gmail Trigger').item.json.threadId }}` — so the draft
  threads onto the original conversation
- `sendTo: {{ … }}` — the recipient, pulled from `decision.draft.to`

No `send`, `sendAndWait` (for Gmail), or any transmit operation.

---

## Rule 3 — No production access during Milestone 1

**Where it's enforced:** policy + the architecture itself.

Everything in this repo points at sandbox credentials and a sandbox Monday
board. The real customer-facing Gmail, the real Drive folder, and the real
Monday board are NOT referenced anywhere in `.env.example`, the workflow
JSON, or any documentation.

`docs/MILESTONE_2_ACCESS.md` lists the access that will be needed for the
real cutover. It is documentation only — no requests have been sent.

---

## Rule 4 — Slack fully removed; approvals via Monday or Gmail internal notes

**Where it's enforced:** workflow structure (Layer 3) + repo grep.

The Milestone 1 workflow (`n8n/fitness-triage.workflow.json`, the v3 version
after Slack removal) must not contain any node whose `type` includes
`slack`. Verify:

```bash
grep -i '"type":.*"slack' n8n/fitness-triage.workflow.json
# (should produce no output)
```

There must also be no Slack credentials configured in the n8n instance, and
no `SLACK_*` environment variables.

The approval path runs through:

- **Monday** (primary) — see Rule 6 below for the idempotency check, plus
  the Approval status column drives a webhook into a separate n8n workflow
  (WF2) that creates the Gmail draft on Approve. WF2 ships at
  `n8n/fs-approval-to-draft.workflow.json`.
- **Gmail internal notes** (secondary) — see
  `docs/GMAIL_INTERNAL_NOTES_SPIKE.md`. The exact feature is awaiting
  clarification from the doc author; in the meantime the Monday card update
  body is the substantive review surface.

---

## Rule 5 — Internal/leadership Gmail triage only

**Where it's enforced:** skill prompt (Layer 1) + JSON schema (Layer 2).

**`scope_gate` is the first skill** in the chain. Before any classification,
SOP lookup, or drafting happens, scope_gate decides whether the email is in
scope at all.

Hard rules in the prompt (verbatim from `~/.openclaw/workspace/skills/scope_gate/SKILL.md`):

1. Customer-facing recipient address (e.g. `sales.cs@`, `support@`,
   `service@`) → `in_scope: false`, `scope_label: "gorgias_owned"`.
2. Internal sender + leadership recipient → `in_scope: true`,
   `scope_label: "leadership"`.
3. Internal sender + internal/operational recipient → `in_scope: true`,
   `scope_label: "internal"`.
4. Anything unclear → `in_scope: false`, `scope_label: "unknown"` (safe
   default).

Schema enforcement (`schemas/scope_gate.json`):

- `scope_label = "gorgias_owned"` REQUIRES `in_scope = false` (conditional
  rule)
- `scope_label = "unknown"` REQUIRES `in_scope = false`
- `scope_label = "internal"` or `"leadership"` REQUIRES `in_scope = true`

So the AI literally cannot produce a contradictory combination — schema
validation rejects it and the chain escalates with a schema error.

When `in_scope = false`, the chain emits `action: "out_of_scope"` and
returns immediately. Nothing downstream runs:

- No classify_email call
- No select_sop call
- No draft_response call
- No audit_check call
- No Monday card created
- No Gmail draft created

**How to verify yourself:** run any customer-facing fixture (case01, case04,
case05, case08, case09) and confirm the resulting decision JSON has
`action: "out_of_scope"`. Then verify nothing downstream happened:

```bash
python3 bin/triage-chain.py fixtures/case04.json /tmp/test-sops.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['action'] == 'out_of_scope', f'expected out_of_scope, got {d[\"action\"]}'
assert d.get('draft') is None, 'no draft should be produced'
print('scope_gate correctly blocked case04')
"
```

---

## Rule 6 — One email = one Monday item

**Where it's enforced:** `bin/monday-card.sh` (Layer 3, bridge code).

**The idempotency check.** Before `monday-card.sh` creates a new card, it
asks Monday: "is there already a card on this board whose Gmail Message ID
column equals this email's `messageId`?" If yes, the script exits cleanly
with a log line and the existing card is reused. If no, the script creates
the card and stamps the column so the next attempt will find it.

The check requires two things to be configured:

- `MONDAY_GMAIL_MSGID_COL_ID` — env var pointing at the text column on the
  board. Set via `.env` and `config/env.sh`.
- The chain providing `decision.email_metadata.messageId` — injected by
  `bin/triage-pipeline.sh` from the email payload's `messageId`. n8n's
  Normalize node already extracts this from the Gmail Trigger output.

Important caveat — **Monday's text column silently strips angle
brackets**. Gmail message IDs are `<...@gmail.com>`. The bridge strips the
angle brackets before write and before lookup so both sides match. This is
already in `monday-card.sh`; do not remove that line.

**How to verify yourself:** pick a decision JSON that has
`email_metadata.messageId` populated and run `monday-card.sh` against it
twice in a row. Confirm the second run logs:

```
[monday] idempotency: card <id> already exists for gmail message_id <id> — skipping create
```

and exits 0 without creating a new card.

---

## Other safety properties (not numbered rules, but load-bearing)

### ACH never auto-drafts

**Where it's enforced:** chain code (Layer 3) + skill prompt (Layer 1) +
schema (Layer 2).

In `triage-chain.py`, when `classify_email` returns
`primary_lane == "Finance / ACH / Owner Approval"`, the chain calls
`make_escalate_decision(approver="Owner")` and returns immediately. The
drafting skill is never invoked.

The `draft_response` SKILL.md also says explicitly:

> When this skill MUST NOT be invoked:
> - When `primary_lane` is `Finance / ACH / Owner Approval`. Finance
>   escalations never receive a customer-facing draft from this skill.

If something upstream slips an ACH email past the early-exit and the chain
calls draft_response anyway, `audit_check` (the final reviewer) is
configured to force-escalate when
`classification.primary_lane == "Finance / ACH / Owner Approval"`. So even a
worst-case bypass still ends in escalation, not a customer-visible draft.

**How to verify yourself:** run `fixtures/case06.json` (vendor ACH) and
confirm the resulting decision has `action: "escalate"`,
`approver_role: "Owner"`, and `draft: null`.

### No-promise list catches subtle violations

The `draft_response` skill prompt enumerates exactly what the draft body
MUST NOT contain:

- Specific refund amounts or refund commitments
- Replacement promises ("we'll send a new one")
- Warranty coverage confirmations
- Specific delivery dates or shipping windows beyond what the SOP says
- Fault or blame statements
- Technical outcome promises

`audit_check` independently re-reads the draft body and force-escalates if
any of these slip in. The check is keyword-tolerant — generic procedural
language mandated by an SOP (e.g. "the Logistics Desk will coordinate
delivery" per SOP-02) is NOT a violation, but an invented commitment is.

### Approver role is always set on every escalation

Every `make_escalate_decision` call in the chain takes an `approver`
argument; the schema for the decision JSON requires `approver_role` to be
present and non-null when `action == "escalate"`. So no escalation can hit
the Monday card without a named human role attached.

---

## Pre-handoff audit checklist (the safety-side subset)

Run before any live demo or client handoff:

```bash
# 1. No-send proof
bash scripts/verify_no_send.sh n8n/fitness-triage.workflow.json

# 2. No Slack
grep -i '"type":.*"slack' n8n/fitness-triage.workflow.json && echo FAIL || echo OK

# 3. Schema integrity — every schema is loadable Draft 7
python3 -c "
import json
from jsonschema import Draft7Validator
import pathlib
for f in pathlib.Path('schemas').glob('*.json'):
    s = json.loads(f.read_text())
    Draft7Validator.check_schema(s)
    print(f'OK: {f.name}')
"

# 4. ACH early-exit
python3 bin/triage-chain.py fixtures/case06_vendor_ach.json /tmp/test-sops.json \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['action'] == 'escalate' and d['approver_role'] == 'Owner' and d.get('draft') is None
print('ACH early-exit: OK')
"

# 5. Scope gate blocks customer-facing
python3 bin/triage-chain.py fixtures/case04.json /tmp/test-sops.json \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['action'] == 'out_of_scope'
print('scope_gate blocking: OK')
"

# 6. Idempotency — pick a real decision file with messageId and run twice
DEC=out/req-<some-id>.decision.json
bash bin/monday-card.sh \"$DEC\"  # first time creates
bash bin/monday-card.sh \"$DEC\"  # second time should say "already exists — skipping create"
```

All six should produce "OK" / "clean" output. Any deviation is a blocker
for the handoff.
