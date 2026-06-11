# Architecture

This is the long-form companion to the README's one-paragraph architecture
summary. It explains why the pieces are split the way they are, what state
lives where, and which constraints drove the design.

---

## The runtime in one sentence

n8n holds every deterministic step (poll Gmail, fetch Drive, branch, create
Monday card, create Gmail draft); OpenClaw holds every reasoning step (the
5 skills); a thin Python bridge sits between them.

---

## The five layers

### Layer 1 — n8n (deterministic plumbing)

Trigger, fan-out to Drive, normalise the payload, call the bridge, branch on
the bridge's reply, create the Gmail draft when appropriate. n8n does NOT
make any judgement calls — it only routes data and creates the structurally
allowed artefacts (drafts in Drafts folder, Monday cards). Everything that
needs an opinion is delegated to OpenClaw via HTTP.

This separation is load-bearing: it lets us audit the deterministic side
purely by reading the workflow JSON (and lets the no-send safety guarantee
be a property of the graph, not a property of any AI behaviour).

### Layer 2 — the bridge (`bin/triage-server.py`)

A tiny HTTP server on `127.0.0.1:8088` whose only job is to receive `{email,
sops}` from n8n, write each piece to `/tmp/req-<id>.{json,sops.json}`, then
shell out to `bin/triage-pipeline.sh`. When the pipeline finishes it
re-reads the decision JSON from `out/req-<id>.decision.json`, augments it
with `email_metadata.threadId` and `email_metadata.messageId` (so WF2 can
thread the post-approval draft onto the original conversation and so the
idempotency check has something to look up), and returns the result to n8n.

It is intentionally tiny — adding logic to the bridge would split reasoning
across two places. The bridge translates protocols; the chain decides.

### Layer 3 — the chain (`bin/triage-chain.py`)

Runs the five OpenClaw skills in sequence:

`scope_gate → classify_email → select_sop → draft_response → audit_check`

After each skill call:

1. Parse the OpenClaw envelope to extract the skill's JSON output.
2. Validate that output against `schemas/<skill>.json` using `Draft7Validator`.
3. If the schema fails: stop. Don't proceed. Emit an escalate (or
   out_of_scope, for scope_gate failures) decision with `schema_errors`
   populated so the audit trail names exactly which field went wrong.

Internal branch points (in chain order):

- `scope_gate.in_scope == false` → emit `action: out_of_scope` and return.
- `classify_email.primary_lane == "Finance / ACH / Owner Approval"` →
  early-exit. ACH is hard-coded to escalate to Owner without ever calling
  the drafting skill. The Finance lane structurally cannot produce a
  customer-facing draft.
- `classify_email.confidence < 70` → early-exit, escalate to CS Lead.
- `select_sop.fallback_action == "route"` → emit `action: route` with a
  `route_to` based on the lane → team map (currently just one entry; expand
  as new internal lanes get added).
- `select_sop.use_for_drafting == false` or `fallback_action == "escalate"`
  → escalate; do not draft.
- `audit_check.force_escalate == true` → escalate; drop the draft.

The chain uses the **SOP source abstraction** (`bin/sop_source.py`) to read
the SOP catalog. Today the only implementation is `InMemorySopSource` which
wraps the list n8n fetched from Drive. In Milestone 2 the production SOP
index slots in as `IndexSopSource` (stub already in place) without touching
the chain or the skill prompts.

### Layer 4 — OpenClaw + the skills

Each skill is one markdown file in the repo at `./skills/<skill>/SKILL.md`,
bind-mounted into the OpenClaw and bridge containers at
`~/.openclaw/workspace/skills/<skill>/SKILL.md` (editing the repo copy is live
in the containers — no rebuild, no restart).
It contains the system prompt, the I/O contract, the hard rules, and the
"forbidden" section.

The five skills and what each one decides:

| Skill | One-sentence purpose | Branch effect |
|---|---|---|
| `scope_gate` | Is this email ours to triage, or Gorgias's? | `in_scope=false` → terminate chain |
| `classify_email` | Which of the 8 lanes does it belong to? | Finance → escalate; low confidence → escalate |
| `select_sop` | Which Active SOP controls? Is there an archived conflict? | `route` → notify team; `use_for_drafting=false` → escalate |
| `draft_response` | Write a customer-safe draft grounded in the SOP. | (always called when chain reaches it) |
| `audit_check` | Final independent review of all the above. | `force_escalate=true` → drop the draft, escalate |

### Layer 5 — Monday + Gmail (the output surfaces)

After the bridge returns the decision to n8n:

- The bridge has already created a Monday card via `bin/monday-card.sh`,
  which posts the full decision JSON (with reasoning, uncommitted_items,
  controlling SOP id, and the proposed draft body when one exists) as the
  card's first update.
- n8n branches on `decision.action`:
  - `draft` → Gmail Create Draft (sets `threadId` from
    `decision.email_metadata.threadId` so the draft lands on the original
    conversation) → workflow ends.
  - `escalate` → workflow ends. The Monday card created by the bridge sits
    with Approval = Awaiting Review. The separate WF2 workflow listens for
    Monday status changes via webhook; when an approver flips Approval to
    Approved, WF2 reads the holding draft from the card update and creates
    the Gmail draft, then flips Approval to Draft Ready.
  - `route` → workflow ends. The card sits in the right lane group with
    `route_to` populated; the assigned team handles it from there.
  - `out_of_scope` → workflow ends. No Monday card, no Gmail draft.

---

## Schemas

`schemas/<skill>.json` is the structural safety net. Every skill output is
validated against its schema before anything downstream consumes it. The
schemas use `additionalProperties: false` so the AI cannot smuggle in extra
fields, and use `allOf` conditional rules to enforce cross-field consistency
(for example: `select_sop.use_for_drafting == true` REQUIRES
`sop_status == "Active"`; `audit_check.pass == true` REQUIRES every other
field to be the no-violations state).

Schema failures stop the chain immediately. The grader can verify this by
running any fixture and confirming `decision.schema_errors` is empty (clean
run) or that a deliberately-malformed prompt produces a non-empty
`schema_errors` with the exact path that failed.

---

## What state lives where

| State | Where it lives | Notes |
|---|---|---|
| Workflows + credentials (n8n) | `n8n_data` Docker volume | wiping this loses every credential the client reconnected; treat as precious |
| Per-request decision JSON | `out/req-<id>.decision.json` (host) and `bridge_out` volume | persistent audit record; rotate by retention policy |
| Per-request email payload | `/tmp/req-<id>.json` (host) | ephemeral; pipe input to the chain |
| SOPs (catalog) | `sops/{active,reference,archived}/*.md` (host) | source-of-truth for sandbox; fetched fresh from Drive in production |
| Skill prompts | `./skills/<skill>/SKILL.md` (repo), bind-mounted into the containers | versioned with the repo; edits are live, no rebuild |
| Skill schemas | `schemas/<skill>.json` | validated at runtime; changing a schema MAY require a prompt change |
| Monday card | the CS Triage board | audit trail per email; idempotent by `gmail_message_id` |
| OpenClaw session keys + provider auth | `~/.openclaw/agents/main/agent/auth-profiles.json` | persistent across restarts; gitignored |
| OpenAI / Monday secrets | `~/secrets/*.key` (host) mode 600 | gitignored; mounted read-only into the bridge container |
| Let's Encrypt certs | `traefik_letsencrypt` Docker volume | rate-limited to re-issue; don't wipe unless needed |

---

## Why each split exists

- **Deterministic vs reasoning** (n8n vs OpenClaw): so safety properties
  (no-send, ACH never auto-drafts, idempotency) can be verified by reading
  the workflow JSON and the bridge code, without trusting any AI behaviour.
- **One skill per decision** (5 separate skills, not one big orchestrator):
  so each skill is independently testable, schema-validated, and
  re-promptable. A failure in classify_email shouldn't taint the audit step.
- **SOP source abstraction** (rather than the chain reading Drive directly):
  so Milestone 2 can swap in a production SOP index without touching the
  chain or the skill prompts.
- **Idempotency at the bridge layer** (rather than in n8n): so the same
  email retried by the Gmail Trigger produces the same Monday card,
  regardless of which workflow happens to call the bridge.
- **`out_of_scope` as a distinct action** (rather than re-using `escalate`):
  so n8n's IF nodes can structurally exit early, with no Monday card and no
  Gmail draft — the cleanest possible "this email doesn't belong here"
  signal.
- **Monday as the structured queue, Gmail Drafts as the staging area**:
  Monday is fast-acting (column flips, automations, audit trail per card);
  Gmail Drafts is where the actual customer-facing artefact lives. Each does
  what it's best at; replacing one with the other loses something important.
