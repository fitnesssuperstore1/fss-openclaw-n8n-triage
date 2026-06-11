# Milestone 1 — Developer Handoff (Master Document)
## Runtime Handoff + Sandbox Deployment

This document consolidates everything from the original Milestone 1 brief and the technical kickoff call into a single source of truth for the dev. Work from this doc.

**Source materials:**
- Original Milestone 1 brief (sent by Arvin)
- Technical kickoff call notes (with Eaunic, Tim, Arvin)
- Stage 2 architecture and codebase (already built — most of this milestone is repackaging)

---

## 0. Headline summary

The system we built in Stage 2 mostly works as-is. Milestone 1 is **not a from-scratch rebuild**. It's a focused set of changes plus packaging the code into a company-controlled GitHub repo with clean deployment instructions.

The major changes are:

1. **Add a scope gate** — block customer-facing/Gorgias-owned email lanes before routing
2. **Remove Slack entirely** — replace with Monday.com tasks and/or Gmail internal notes
3. **Add 5 new internal/leadership test cases** alongside the original 10
4. **Move all runtime code into the company's private GitHub repo** — no secrets, clean commit history
5. **Deliver a clear README/runbook** that lets the client set up the system without our help
6. **Prepare for a live handoff call** where the client imports our n8n workflow and verifies safety properties themselves

Everything else from Stage 2 stays.

---

## 1. The 5 hard rules (confirmed on kickoff — cannot be violated)

These are absolute. Verify each one in the final delivery.

| # | Rule | How we prove it |
|---|------|-----------------|
| 1 | No Gmail Send / Reply / SMTP node anywhere in the n8n workflow | Inspect the imported workflow — only "Gmail Create Draft" nodes exist |
| 2 | Gmail Create Draft only | Same as above |
| 3 | No production access during Milestone 1 — sandbox/mock data only | All work happens in the sandbox; production-access list is documented but not requested |
| 4 | Slack fully removed — approvals via Monday.com or Gmail internal notes only | No Slack node, no Slack credentials, no Slack code references anywhere |
| 5 | Internal/leadership Gmail triage only — customer-facing lanes blocked by scope gate | Scope gate skill runs first; customer-facing lanes exit immediately |
| 6 | **One email = one Monday item** (no duplicates) | Idempotency check on Gmail `message_id` before Monday card creation |

Rule 6 is new emphasis from the kickoff — Eaunic said it twice. Treat it as load-bearing.

---

## 2. What was clarified on the kickoff call

A few details that change or sharpen the original brief:

### 2.1 Monday.com structure already exists

Their team has an existing Monday board with automation already creating tasks ("task lists" in their language) for incoming emails. We are NOT inventing a board structure. We integrate with the existing one.

**Action item:** when their developer reaches out (expected within ~3 hours of kickoff), get:
- Board ID
- Column names and structure
- Group/lane naming convention
- Any existing automation that might conflict with what we're building

### 2.2 Approval surfaces

Two valid approval mechanisms confirmed on the call:
- **Monday.com tasks** — primary structured queue
- **Gmail internal notes** — inline reviewer comments on the draft itself (Gmail's feature where notes can be attached to a draft without being visible to the customer)

We currently don't have Gmail internal notes integrated. **This is a small gap to close** as part of Milestone 1. Use it for cases where inline draft commentary makes more sense than a Monday task (e.g. CS Lead leaving a note like "approved, send as-is" or "rewrite paragraph 2").

### 2.3 No production access

Confirmed again on the call — no production credentials, no real customer emails, no real Drive folder, no real Monday board. Everything stays in our sandbox throughout Milestone 1. Production access discussion is part of Milestone 2 planning, not Milestone 1 delivery.

### 2.4 Final handoff includes a live verification call

The client will import the n8n workflow JSON into their own n8n instance and inspect it themselves. Specifically:
- They will visually confirm no Send/Reply/SMTP nodes exist
- They will trace the Finance/ACH lane to confirm early-exit (no draft created)
- They will run a fixture or two to confirm schema validation works

**Implication:** the workflow export must be clean. No orphan nodes, no disabled-but-still-present Send nodes, no dead branches that reference Slack. Audit before exporting.

### 2.5 Communication and pace

- Primary contact: Eaunic (on Upwork)
- Secondary: Arvin
- Both will be available via email
- If blocked and no response within 2-24 hours → keep moving on other items, don't wait

This is a gift. It means we can move fast without bottlenecking on every clarification.

### 2.6 Branch strategy

All work on a `milestone-1` branch with a clear commit history. No squashed mega-commits at the end. Logical, reviewable commits.

---

## 3. Codebase work — what changes, what stays

### 3.1 What stays exactly as-is

Most of the Stage 2 codebase carries over unchanged:

- `bin/triage-server.py` — HTTP bridge on :8088 (no changes)
- `bin/triage-chain.py` — 4-skill orchestrator (small change: add scope_gate as new first skill)
- `bin/triage-pipeline.sh` — end-to-end orchestrator (no changes)
- `bin/extract_decision.py` — unchanged
- `schemas/classify_email.json` — unchanged
- `schemas/select_sop.json` — unchanged
- `schemas/draft_response.json` — unchanged
- `schemas/audit_check.json` — unchanged
- All 4 existing SKILL.md files — unchanged
- Existing 10 case fixtures — unchanged

### 3.2 What changes

**3.2.1 — Add the scope_gate skill (NEW)**

A new fifth skill that runs first in the chain.

Files to add:
- `skills/scope_gate/SKILL.md`
- `schemas/scope_gate.json`

Skill purpose: decide if the email is internal/leadership (in scope) or customer-facing/Gorgias-owned (out of scope) before any routing decisions.

Output schema:
```json
{
  "in_scope":    boolean,
  "scope_label": "internal | leadership | gorgias_owned | unknown",
  "reason":      "one-sentence explanation",
  "signals":     ["array of keywords/phrases that drove the decision"]
}
```

Hard rules in the prompt:
- If the `to` field contains `sales.cs@`, `shipping.cs@`, `support@frenchfitness.com`, `service@`, or any other customer-facing inbox → `in_scope: false`, `scope_label: "gorgias_owned"`
- If sender is internal AND recipient is a leadership inbox → `in_scope: true`, `scope_label: "leadership"`
- If sender is internal AND recipient is operational/internal inbox → `in_scope: true`, `scope_label: "internal"`
- If unclear → `in_scope: false`, `scope_label: "unknown"` (safe default; do not process)

When `in_scope: false`:
- No `classify_email` call
- No `select_sop` call
- No `draft_response` call
- No `audit_check` call
- No Monday item created
- No Gmail draft created
- Write a sandbox audit log entry recording the out-of-scope classification

**3.2.2 — Modify `triage-chain.py`**

Add scope_gate as the first skill call. Validate output against `schemas/scope_gate.json`. On `in_scope: false`, return early with a decision JSON like:

```json
{
  "action": "out_of_scope",
  "scope_label": "...",
  "reason": "...",
  "draft": null,
  "monday_item": null
}
```

Everything downstream (n8n branches, Monday integration) needs to recognize the new `out_of_scope` action and do nothing customer-visible.

**3.2.3 — Remove Slack from the n8n workflow**

⚠️ **Critical: do NOT modify the live Stage 2 workflow.** Make a copy.

Steps:
1. Duplicate the existing `FS — Inbound Triage v2` workflow → save as `FS — Inbound Triage v3 (Milestone 1)`
2. In v3 only: delete the Slack "Send and wait for response" node (approvals)
3. In v3 only: delete the Slack "Send message" node (internal task notifications)
4. Replace with Monday.com nodes (see 3.2.4)
5. v1 stays untouched and still available for client inspection

Add an `out_of_scope` branch in the workflow: when the chain returns `action: out_of_scope`, the workflow logs it (optionally to a sandbox audit Sheet) and exits. No Monday item, no Gmail draft, nothing customer-visible.

**3.2.4 — Replace Slack with Monday.com approvals**

Pattern to implement (TBD on confirmation from the client's developer, but starting plan):

For escalation cases (Cases 6, 8, plus the new internal ACH case):
- Create the Monday task in the appropriate group on the existing CS Triage board
- Set a status column to "Awaiting Approval"
- Use a Monday webhook (or n8n's Monday trigger) to listen for status column changes
- When the status flips to "Approved" or "Rejected", continue or stop the workflow accordingly

For internal task routing (Case 7-style):
- Create the Monday task assigned to the right team
- No approval gate needed; the task itself IS the routing

For Gmail internal notes:
- When a draft is created and the approver wants to leave inline commentary, we use Gmail's draft note feature
- This is supplementary to Monday, not a replacement — Monday is the structured queue, Gmail notes are inline comments

**3.2.5 — Idempotency check**

Before creating a Monday item, query the existing board for any item already tagged with the same Gmail `message_id`. If one exists, do not create a duplicate. Update the existing one instead (or no-op if state is unchanged).

Implementation:
- Add a custom column on Monday: `gmail_message_id` (text)
- On every Monday create call, search for items where `gmail_message_id == current message_id`
- If found, update; if not, create

This satisfies Rule 6 (one email = one Monday item).

**3.2.6 — Add 5 internal/leadership test fixtures**

Templates from the brief (write actual email JSON for each):

1. **Tim asks which SOP controls a workflow.** Internal team member asking about SOP governance.
   - Example: "Hey team, which SOP do we follow for handling vendor onboarding requests right now? I see SOP-12 and REF-04 both mention it."

2. **Arvin asks who owns or manages a process.** Leadership asking for process ownership clarity.
   - Example: "Who currently owns the Monday board for shipping CS? I need to update some access permissions."

3. **Operations asks whether an email belongs in Gorgias or internal handling.** Meta-question about scope gate itself.
   - Example: "Got an email from a customer about a freight delay — does this go through our internal Gmail triage or is this fully Gorgias-owned now?"

4. **Vendor ACH/payment request lands in a leadership inbox.** ACH safeguard in internal context.
   - Example: "Please confirm the wire transfer for invoice #94821, $24,300. Updated routing info attached." (sent to leadership@, not accounts-payable@)

5. **Internal product/content/SOP cleanup request.** Like the existing Case 7 but coming from leadership/operations.
   - Example: "The Q2 product specs sheet on Drive needs an update — three of the items have wrong dimensions. Can someone on the content team grab this?"

Place fixtures in `fixtures/internal_*.json` with the same schema as the existing 10:

```json
{
  "from": "...",
  "to": "...",
  "subject": "...",
  "body": "...",
  "received_at": "ISO timestamp",
  "expected_outcome": {
    "in_scope": true | false,
    "scope_label": "...",
    "primary_lane": "...",
    "action": "draft | route | escalate | out_of_scope",
    "approver_role": "..." 
  }
}
```

**3.2.7 — Refactor SOP source layer behind an abstraction**

Production will replace our filename-convention Drive lookup with a real SOP Index/RAG system. We don't know its shape yet, so build the abstraction now and swap implementations in Milestone 2.

Create a clean interface:

```python
class SopSource:
    def list_sops(self, lane: str) -> list[Sop]:
        raise NotImplementedError

    def get_sop(self, sop_id: str) -> Sop | None:
        raise NotImplementedError
```

Implement:
- `DriveSopSource` — current behavior, reads Drive folders, tags by filename prefix
- Stub `IndexSopSource` — placeholder that returns the same shape, to be wired in Milestone 2

The rest of `triage-chain.py` and the `select_sop` skill consume the abstraction. They should not know which source is in use.

**Verify:** the existing 10-case regression must still pass after the refactor. No behavior change.

---

## 4. GitHub deployment — the company-controlled repo

### 4.1 Waiting for the repo

The client's developer will create a private repo and send the invite within ~3 hours of the kickoff. We push our work there. No personal repo.

### 4.2 Repository structure (push this skeleton)

```
fitness-superstore-triage/
├── README.md                       ← runbook, comprehensive
├── docker-compose.yml              ← sandbox-ready, parameterized via .env
├── .env.example                    ← all required env vars, no real values
├── .gitignore                      ← excludes .env, secrets/, *.key, *.pem
├── LICENSE                         ← if the client specifies
├── CHANGELOG.md                    ← optional but professional
│
├── bin/
│   ├── triage-server.py            ← HTTP bridge on :8088
│   ├── triage-chain.py             ← 5-skill orchestrator (was 4)
│   ├── triage-pipeline.sh          ← end-to-end runner
│   ├── triage-one.sh               ← single fixture runner
│   ├── extract_decision.py
│   └── monday-card.sh              ← Monday API client
│
├── config/
│   ├── env.sh.example              ← template only
│   └── monday-groups.json          ← lane → Monday group mapping
│
├── schemas/
│   ├── scope_gate.json             ← NEW
│   ├── classify_email.json
│   ├── select_sop.json
│   ├── draft_response.json
│   └── audit_check.json
│
├── skills/
│   ├── scope_gate/SKILL.md         ← NEW
│   ├── classify_email/SKILL.md
│   ├── select_sop/SKILL.md
│   ├── draft_response/SKILL.md
│   └── audit_check/SKILL.md
│
├── n8n/
│   └── fitness-triage.workflow.json  ← v3 export, post-Slack-removal
│
├── fixtures/
│   ├── case_01_unshipped_eta.json
│   ├── case_02_freight_tracking.json
│   ├── case_03_mixed_shipping_install.json
│   ├── case_04_damage_refund.json
│   ├── case_05_financing.json
│   ├── case_06_vendor_ach.json
│   ├── case_07_internal_product_page.json
│   ├── case_08_gorgias_conflict.json
│   ├── case_09_parcel_missing.json
│   ├── case_10_archived_sop_conflict.json
│   ├── internal_01_sop_question.json   ← NEW
│   ├── internal_02_process_ownership.json   ← NEW
│   ├── internal_03_gorgias_vs_internal.json   ← NEW
│   ├── internal_04_leadership_ach.json   ← NEW
│   └── internal_05_internal_cleanup.json   ← NEW
│
├── docs/
│   ├── ARCHITECTURE.md             ← system overview
│   ├── SAFETY.md                   ← four-layer enforcement, no-send proof, ACH early-exit
│   ├── DEPLOYMENT.md               ← step-by-step setup
│   ├── TESTING.md                  ← how to run all 15 fixtures
│   └── MILESTONE_2_ACCESS.md       ← list of access needed for production
│
└── scripts/
    ├── run_all_fixtures.sh         ← regression test runner
    └── verify_no_send.sh           ← audit script that greps the n8n JSON for forbidden node types
```

### 4.3 Critical security rules for the repo

These are non-negotiable. Violating any of these is grounds for losing the contract.

- **No secrets in any commit.** Not in `.env`, not in `config/env.sh`, not in any test fixture, not in a comment, not even temporarily. If a secret is committed even once, it lives in git history forever.
- **`.gitignore` must exclude:** `.env`, `env.sh`, `secrets/`, `*.key`, `*.pem`, `*.p12`, `*.pfx`, `credentials.json`, `token.json`, `*.sqlite`, any file path containing the word `secret` or `private`.
- **`.env.example` lists every required env var** with placeholder values like `OPENAI_API_KEY=sk-replace-me`. Never a real key.
- **`config/env.sh.example`** lists every required shell var with placeholders. The real `env.sh` lives outside the repo on the deploying machine.
- **All credentials are company-owned and rotatable.** No keys from our personal accounts. The client provides their own OpenAI key, Monday token, Google OAuth client, etc.
- **Before every commit, run:** `git diff --cached | grep -iE 'sk-[a-z0-9]{20,}|api[_-]?key|password|secret|token' | grep -v 'example'` — if anything matches, do not commit.

### 4.4 Branch strategy

- All work on `milestone-1` branch
- Commit history must be reviewable — logical commits, descriptive messages, no "wip" or "fix" alone
- Suggested commit progression:
  1. Initial repo structure + `.gitignore` + `.env.example`
  2. Copy of existing 4 SKILL.md files and 4 schemas
  3. Add scope_gate SKILL.md and schema
  4. Add scope_gate integration in `triage-chain.py`
  5. Refactor SOP source layer behind abstraction
  6. Remove Slack from n8n workflow (export v3 JSON)
  7. Add Monday.com approval integration
  8. Add idempotency check by `message_id`
  9. Add 5 internal test fixtures
  10. Update README and docs
  11. Add no-send audit script
  12. Final regression run output committed to docs

Each commit should leave the system in a working state (or at minimum, the tests in a known state). The client will read this history.

### 4.5 docker-compose.yml for sandbox

The compose file should bring up the full sandbox with one command. Parameterize via `.env`:

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    environment:
      - N8N_HOST=${N8N_HOST}
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=${N8N_WEBHOOK_URL}
      - GENERIC_TIMEZONE=${TIMEZONE}
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
    ports:
      - "5678:5678"

  openclaw:
    # whatever the OpenClaw image/build setup is
    # ...

  triage-bridge:
    build: .
    restart: unless-stopped
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MONDAY_API_TOKEN=${MONDAY_API_TOKEN}
      - MONDAY_BOARD_ID=${MONDAY_BOARD_ID}
    volumes:
      - ./bin:/app/bin:ro
      - ./schemas:/app/schemas:ro
      - ./skills:/app/skills:ro
    network_mode: host  # bridge needs to reach OpenClaw on localhost

volumes:
  n8n_data:
```

Test that `docker compose up -d` brings everything online cleanly from a fresh clone. The client should be able to do this without our help.

### 4.6 .env.example template

```bash
# OpenAI / Anthropic API
OPENAI_API_KEY=sk-replace-me

# Google OAuth (for Gmail + Drive)
GOOGLE_CLIENT_ID=replace-me
GOOGLE_CLIENT_SECRET=replace-me
GOOGLE_REFRESH_TOKEN=replace-me

# Monday.com
MONDAY_API_TOKEN=replace-me
MONDAY_BOARD_ID=replace-me

# n8n
N8N_HOST=n8n.example.com
N8N_WEBHOOK_URL=https://n8n.example.com/
N8N_USER=admin
N8N_PASSWORD=replace-me

# Timezone
TIMEZONE=America/New_York
```

---

## 5. README / runbook content

The client said: "very clear, precise, straight to the point" — and that they should be able to set up the system "without you explaining it."

Treat the README as the deliverable, not a courtesy. The dev who reads it should be able to:

1. Clone the repo
2. Provision credentials
3. Bring up the stack
4. Import the n8n workflow
5. Run a fixture end-to-end
6. Verify the safety properties

…all without asking us anything.

### Section structure

```markdown
# Fitness Superstore — Inbound Email Triage

## What this system does
(One paragraph)

## Architecture
(Diagram + brief explanation of the 5-skill chain + n8n + Monday)

## Prerequisites
- Docker + Docker Compose
- A domain pointing at the host server (for n8n's HTTPS)
- OpenAI / Anthropic API key
- Google Cloud project with Gmail + Drive OAuth client
- Monday.com API token + a board ID with the expected group structure
- OpenClaw installed and running

## Quick start
1. Clone the repo
2. Copy `.env.example` to `.env` and fill in values
3. Run `docker compose up -d`
4. Import `n8n/fitness-triage.workflow.json` into n8n
5. Remap credentials in n8n (Gmail, Drive, Monday)
6. Activate the workflow
7. Send a test email to the inbox; verify a draft appears in Gmail and a card in Monday

## Running fixtures
- Run all: `bash scripts/run_all_fixtures.sh`
- Run one: `python3 bin/triage-chain.py fixtures/case_01_*.json /tmp/sops.json`
- Output: per-fixture decision JSON + stderr trace

## Safety verification
### No-send proof
- Open the imported n8n workflow
- Confirm no nodes of type Gmail Send, SMTP, Reply, or Forward exist
- Run `bash scripts/verify_no_send.sh n8n/fitness-triage.workflow.json` — should exit 0

### ACH early-exit proof
- Send fixture case_06_vendor_ach.json through the chain
- Verify Finance lane is matched
- Verify no Gmail draft is created (Drafts folder remains empty)
- Verify Monday task is created with status "Awaiting Owner Approval"

### Scope gate proof
- Send any of fixtures/case_01–case_10 except case_06 and case_07 to the scope gate alone
- For customer-facing addresses, verify the workflow exits with action: out_of_scope

## Operational notes
- Audit logs: where they live, how to rotate
- Monitoring: how to check for stuck Monday approvals
- Adding a new SOP: process
- Adding a new test fixture: process

## Troubleshooting
- Schema validation failures
- OpenClaw not reachable
- Drive auth issues
- Monday card not created
- n8n trigger not firing
```

Write the README as you build, not at the end. Each commit should keep it current.

---

## 6. Live handoff call prep

At the end of the milestone, the client will run a call where they import the n8n workflow JSON and inspect it themselves. They will specifically check:

- **No-send proof:** open the workflow, scan for any Send/Reply/SMTP node. There must be none.
- **ACH early-exit proof:** trace the Finance lane in the workflow editor; confirm it bypasses the draft skill entirely.
- **Schema validation:** they may run one fixture through the chain to confirm schema_errors[] comes back empty.
- **Monday integration:** they may verify the workflow creates a Monday task and listens for approval status changes.

### Pre-handoff audit checklist (run this BEFORE the call)

- [ ] Export the n8n workflow as JSON; manually inspect for any Send/Reply/SMTP/Forward node — there must be zero
- [ ] Confirm the JSON imports cleanly into a fresh n8n instance (test this on a side instance)
- [ ] Confirm all credential references in the JSON are placeholder IDs that the client will remap
- [ ] Confirm the `out_of_scope` branch is wired and doesn't create any artifacts
- [ ] Run all 15 fixtures (10 original + 5 new) through the chain; capture decision JSONs and confirm zero schema errors
- [ ] Confirm the Finance lane fixture (case_06) produces no Gmail draft
- [ ] Confirm the scope_gate skill exits early on the customer-facing fixtures
- [ ] Confirm the idempotency check works (run the same fixture twice; only one Monday task should result)
- [ ] Walk through the README from a fresh-clone perspective; fix anything ambiguous

---

## 7. Tasks already started (from the prep handoff)

If you already started on the prep tasks I sent earlier, here's what carries over:

- ✅ `scope_gate` skill scaffold — keep building; the schema and prompt rules above are the final shape
- ✅ SOP source layer abstraction — finish; this is now formal scope, not just prep
- ✅ n8n workflow duplication (v2 → v3, Slack removed) — keep; this becomes the milestone deliverable
- ✅ Local GitHub repo skeleton — once the company repo is provisioned, push the skeleton there as the first commit
- ✅ README/runbook draft — expand using the structure in Section 5 above
- ✅ 5 internal test case fixtures — finalize using the examples in Section 3.2.6 above
- ✅ Slack-coupled code surface audit — use this to plan the removal cleanly

---

## 8. What's NEW vs. the prep handoff

These items were not in the earlier prep handoff and need attention:

1. **Idempotency by Gmail message_id** — new requirement from the kickoff (Rule 6). Must be implemented in the Monday integration.
2. **Gmail internal notes integration** — confirmed as a valid approval surface. Research Gmail's API for draft notes and integrate as a supplementary approval channel.
3. **`out_of_scope` action type** — new decision action that the chain returns and n8n branches on. Must be plumbed through.
4. **No-send audit script** — `scripts/verify_no_send.sh` that greps the n8n JSON for any Send-related node type. Useful for CI and for the live handoff call.
5. **Live handoff prep** — see Section 6 above. The exported workflow must be inspection-ready.
6. **`docs/MILESTONE_2_ACCESS.md`** — a documented list of access we'll need for the production cutover. This is a Milestone 1 deliverable, not just notes.

---

## 9. Definition of done

The milestone is complete when:

- [ ] All code is in the company GitHub repo on the `milestone-1` branch
- [ ] No secrets in any commit (verified by git history scan)
- [ ] `.env.example` lists every required env var
- [ ] `docker compose up -d` brings the stack online from a fresh clone
- [ ] n8n workflow JSON imports cleanly into a fresh n8n instance
- [ ] All 15 fixtures (10 original + 5 internal) pass with zero schema errors
- [ ] Scope gate correctly blocks customer-facing/Gorgias lanes
- [ ] Finance/ACH lane produces no Gmail draft
- [ ] Idempotency check prevents duplicate Monday items for the same Gmail message_id
- [ ] No Slack code or references anywhere in the codebase
- [ ] No Send/Reply/SMTP/Forward node anywhere in the n8n workflow
- [ ] README is comprehensive enough that a stranger can deploy from scratch
- [ ] Monday integration works for both approval status changes and internal task routing
- [ ] Gmail internal notes integration works for inline draft commentary
- [ ] `docs/MILESTONE_2_ACCESS.md` documents the access list for production cutover
- [ ] Pre-handoff audit checklist (Section 6) passes
- [ ] Final commit is clean; commit history is logical and reviewable

---

## 10. Safety reminders (read before every work session)

- Do NOT modify the live Stage 2 workflow. The client still has access. Make a copy.
- Do NOT commit any secret, even temporarily. Git history is forever.
- Do NOT request production access. This is sandbox-only until Milestone 2.
- Do NOT touch the production Drive folder, real Gmail account, or production Monday board.
- Do NOT introduce any node into n8n that can send a customer-visible message. Drafts only.
- Do NOT skip schema validation when adding scope_gate. Same rigor as the other four skills.

---

## 11. Communication and escalation

- Primary contact: Eaunic (Upwork DMs)
- Secondary: Arvin (Upwork or email)
- The client's dev: TBD (will reach out within ~3 hours of kickoff with GitHub repo invite + Monday board details)
- The architect (Yonatan): available for daily sync, blocker triage, design questions

If blocked and waiting on the client side: keep moving on other items. Don't sit idle. The client explicitly said "if no response in 2-24 hours, move forward with other items."

---

## 12. Risks and watch-outs

| Risk | Mitigation |
|------|-----------|
| Their Monday board structure differs from what we assume | Get the board ID + column structure from their dev before wiring; if mismatch, ask before building |
| Gmail internal notes API has gotchas we haven't seen | Build a small spike first; verify it works before integrating into the main flow |
| The client's developer is slow to provision the GitHub repo | Keep work moving locally; push when ready. Escalate to Eaunic after 6 hours if no invite |
| The live handoff call surfaces a node we missed | Pre-handoff audit (Section 6) catches these. Run the audit twice |
| Scope gate misclassifies an edge-case email | Add the case to fixtures, refine the prompt, re-run. The fixtures are the regression set |
| Idempotency check fires on Monday but the workflow already created the card | Add error handling: if the Monday create call fails due to duplicate, log a warning and proceed (don't crash the workflow) |
| Stage 2 workflow (v1) gets broken accidentally | Hard rule: don't touch v1. Work on v3 only |
| Secret accidentally committed | Run `git filter-repo` to remove from history; rotate the secret immediately; tell the client we caught and fixed it |

---

## End

Work this doc top to bottom. Flag anything unclear before starting that section. The architect is available for design sync as needed.
