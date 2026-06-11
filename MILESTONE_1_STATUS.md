# Milestone 1 — Status

## Done

- ✅ scope_gate skill + JSON schema
- ✅ triage-chain.py wired to call scope_gate first
- ✅ SOP source abstraction (InMemorySopSource + IndexSopSource stub)
- ✅ 10 original fixtures updated with `to:` field
- ✅ 5 new internal/leadership fixtures
- ✅ All 15 fixtures run clean (0 schema errors)
- ✅ classify_email Rule 2 (internal meta-question) added
- ✅ Slack fully removed from n8n
- ✅ n8n v3 workflow duplicated and cleaned
- ✅ Monday `Approval` column + WF2 handles escalate flow
- ✅ Monday `gmail_message_id` column for idempotency
- ✅ `monday-card.sh` skips out_of_scope decisions
- ✅ `monday-card.sh` idempotency check (one email = one card)
- ✅ Normalize email node extracts `to:` field
- ✅ `triage-pipeline.sh` injects `email_metadata` (threadId, messageId)
- ✅ Gmail internal notes spike — doc author clarification needed
- ✅ `.gitignore`, `.env.example`, `config/env.sh.example`, `docker-compose.yml`
- ✅ `README.md` + 5 docs (Architecture, Safety, Deployment, Testing, Milestone 2 Access)
- ✅ `scripts/run_all_fixtures.sh`
- ✅ `scripts/verify_no_send.sh`
- ✅ Pre-handoff audits (no-send, credential refs, schema-clean, ACH no-draft, scope_gate blocking)

## Left

- ⏸️ GitHub repo invite, push, milestone-1 branch — waiting on client repo
- ⏸️ Gmail internal notes wiring — waiting on doc author to clarify which tool they meant

---

## What scope_gate checks (current rules)

Applied top to bottom; first match wins.

1. **`to:` contains customer-facing tag** (`sales@`, `support@`, `service@`, `cs@`, `customer@`, `help@`, `returns@`, `sales.cs@`, `shipping.cs@`) → **out_of_scope (gorgias_owned)**.
2. **`to:` contains leadership tag** (`leadership@`, `owner@`, `ceo@`, `cto@`, `coo@`, `directors@`, `executive@`) **AND sender looks internal** → **in_scope (leadership)**.
3. **`to:` contains internal/operational tag** (`team@`, `ops@`, `triage@`, `internal@`, `content@`, `merch@`, `warehouse@`, `logistics@`, `accounts@`, `accounts-payable@`, `finance@`, `product@`) **AND sender looks internal** → **in_scope (internal)**.
4. **Anything else** → **out_of_scope (unknown)** (safe default).

**"Sender looks internal"** if any of:
- Company-domain `from:` address
- Body signed as `warehouse`, `ops`, `merch`, `product`, `finance`, `accounts`, `logistics`
- Subject contains `[internal]`, `[team]`, or `[ops]`
- Body addresses "team" with no customer context
