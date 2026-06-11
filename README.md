# Fitness Superstore — Inbound Email Triage (Phase 1 sandbox)

A Gmail-only triage system that classifies inbound internal/leadership email,
matches it to the controlling SOP, and either drafts a holding reply (for
human approval) or routes the task to the right team in Monday. **Nothing in
this system can ever send an email to a customer** — the workflow is wired
draft-only by structure.

This README is the deployment runbook. A reader who has never seen the project
should be able to clone the repo, fill in credentials, bring the stack up,
import the n8n workflow, and verify safety properties without asking us.

---

## What the system does

An email arrives at the triage Gmail inbox. n8n picks it up and runs it through
a five-skill OpenClaw chain that, in order:

1. **scope_gate** — decides if the email is in scope at all (internal /
   leadership) or belongs to Gorgias (customer-facing). Out-of-scope emails
   terminate the chain immediately.
2. **classify_email** — picks one of 8 workflow lanes plus an optional
   secondary, with confidence.
3. **select_sop** — picks the controlling Active SOP for that lane, flagging
   any archived-vs-active conflict for the audit trail.
4. **draft_response** — writes a customer-safe draft reply grounded in the
   matched Active SOP, with anything the customer asked for that the draft
   refuses to commit recorded in `uncommitted_items[]`.
5. **audit_check** — final independent reviewer. Force-escalates if anything
   upstream is inconsistent or the draft violates the no-promise list.

Every skill response is schema-validated against `schemas/<skill>.json`
**before** the chain proceeds. Schema failure stops the chain and escalates.

The chain returns a unified decision JSON. n8n branches on the decision:

- `action: draft` → Gmail Create Draft (in the Drafts folder; never sent)
- `action: escalate` → Monday card with Approval = Awaiting Review (approver
  flips it to Approved/Rejected; a separate webhook-triggered workflow then
  creates the Gmail draft if a holding draft exists in the decision)
- `action: route` → Monday card in the right lane group with route_to set; no
  customer-facing draft
- `action: out_of_scope` → terminate; no Monday card, no draft, no customer
  contact

Every result lands as a Monday card with the full decision in the card update
body, so the human reviewer has every signal in one place.

---

## Architecture

Everything runs from **one `docker-compose.yml`** with five services:

| Service | What it is | Key mounts |
|---|---|---|
| `traefik` | reverse proxy + HTTPS (Let's Encrypt) | `./infra/traefik/` — static config, dynamic routes, and the cert store (`acme.json`) |
| `openclaw` | the agent gateway (Control UI + agent runtime) | `./skills` **bind-mounted** into the workspace; state on the `openclaw_data` volume |
| `n8n-import` | one-shot seeder — imports `./n8n/workflows/*.json` on first boot, then exits (skips when workflows already exist) | `./n8n/workflows` (read-only) + the shared `n8n_data` volume |
| `n8n` | workflow engine (Gmail trigger, Drive fetch, branching, Gmail Create Draft) — waits for `n8n-import` to finish | `n8n_data` volume |
| `bridge` | the triage HTTP server (`bin/triage-server.py` on `127.0.0.1:8088`) — built **from the same image as `openclaw`** because the chain shells out to the `openclaw` CLI per skill call | project mounted at `/root/Arvin` (the path the `bin/` scripts expect), `./skills` in its workspace, `~/secrets` read-only, its own agent-state volume |

**The folder-bind pattern (important):** skills are NOT baked into any image
and NOT copied into a volume. The repo's `./skills/<name>/SKILL.md` files are
bind-mounted directly into both the `openclaw` and `bridge` containers —
**editing a skill on the host is live in the containers immediately**, no
rebuild, no restart. Same idea for n8n: workflow JSONs live in
`./n8n/workflows/` and get imported by the one-shot `n8n-import` service
(workflows only — credentials are connected by hand in the n8n UI, never
stored in the repo).

```
  Gmail Trigger ─▶ Normalize ─▶ Drive Search+Download ─▶ Build payload
   (n8n service)                                                │
                                                                ▼
                                                    HTTP POST /triage
                                                                │
                                                                ▼
                       ┌────────── bridge container (:8088) ─────────────────┐
                       │   triage-pipeline.sh                                │
                       │      triage-chain.py:                               │
                       │        scope_gate ─▶ classify_email ─▶ select_sop  │
                       │          ─▶ draft_response ─▶ audit_check          │
                       │        (each skill = `openclaw agent --local`,      │
                       │         skills bind-mounted from ./skills)          │
                       │      monday-card.sh   (creates the card)            │
                       └─────────────────────────────────────────────────────┘
                                                                │
                                       decision JSON returned   │
                                                                ▼
                                           n8n IF (action) ────────────────▶
                                                                │
                                  ┌──────────┬──────────┬──────────┐
                                  ▼          ▼          ▼          ▼
                                draft    escalate     route    out_of_scope
                                  │          │          │          │
                          Gmail Create Draft │   (already done by Monday card)
                                             ▼
                                    (Monday Approval column drives WF2,
                                     which creates the Gmail draft on Approve)
```

---

## Prerequisites

| What | Why |
|---|---|
| Docker + the Docker Compose plugin | runs the whole stack — traefik, openclaw, n8n, n8n-import, bridge |
| A domain pointing at the host server | n8n needs HTTPS for Gmail OAuth and Monday's webhook |
| Two DNS subdomains (e.g. `n8n.<domain>`, `openclaw.<domain>`) pointing at the box | Traefik routes per subdomain |
| OpenAI or Anthropic API key | every skill call; ~5 per inbound email |
| Google Cloud project with OAuth client | Gmail trigger + Drive SOP fetch (authorized redirect URI must include the n8n callback) |
| Monday.com workspace + a board | structured queue + audit trail. Needs: 8 lane groups, Approval status column, Gmail Message ID text column |

Everything else (OpenClaw, the openclaw CLI, python3, jsonschema, jq) lives
inside the images — nothing besides Docker is installed on the host.

---

## Quick start

1. **Clone the repo.**

   ```bash
   git clone <repo-url> fitness-superstore-triage
   cd fitness-superstore-triage
   ```

2. **Copy the example env files and fill in real values.** None of the real
   values ever get committed.

   ```bash
   cp .env.example .env
   cp config/env.sh.example config/env.sh
   $EDITOR .env
   $EDITOR config/env.sh
   ```

3. **Put raw secrets in `~/secrets/` on the host.** The bridge expects:

   ```bash
   mkdir -p ~/secrets
   chmod 700 ~/secrets
   printf '%s' '<openai-key>' > ~/secrets/openai.key && chmod 600 ~/secrets/openai.key
   printf '%s' '<monday-token>' > ~/secrets/monday.key && chmod 600 ~/secrets/monday.key
   ```

4. **Provision Monday board structure** if the board is new:
   - Create 8 groups, one per workflow lane (names exactly as in
     `config/monday-groups.json`).
   - Create a status column called `Approval` with labels:
     `Awaiting Review | Approved | Rejected | Draft Ready | Sent`.
   - Create a text column called `Gmail Message ID`.
   - Record the column ids in `.env` (`MONDAY_APPROVAL_COL_ID`,
     `MONDAY_GMAIL_MSGID_COL_ID`) and in `config/monday-groups.json` (one
     entry per lane → group id).

5. **Start the stack.**

   ```bash
   docker compose up -d
   docker compose logs -f --tail=50
   ```

6. **Connect credentials in the n8n UI** (https://n8n.<domain>):
   - Workflows are imported automatically on first boot — the one-shot
     `n8n-import` service seeds everything in `n8n/workflows/` (it skips on
     restarts so it never duplicates or overwrites).
   - Create the credentials in this instance (Gmail OAuth2, Google Drive
     OAuth2, Monday API) and re-map each workflow node to them — credential
     references in the seeded JSONs are placeholders that the import cannot
     resolve.
   - Activate the workflows.

7. **Subscribe Monday's webhook to WF2** (the approval-to-draft workflow).
   In the WF2 webhook node, copy the production URL. Then:

   ```bash
   curl -s https://api.monday.com/v2 \
     -H "Authorization: $MONDAY_API_TOKEN" \
     -H "Content-Type: application/json" \
     -H "API-Version: 2024-10" \
     -d "{\"query\":\"mutation { create_webhook(board_id: $MONDAY_BOARD_ID, event: change_specific_column_value, url: \\\"<wf2-prod-url>\\\", config: \\\"{\\\\\\\"columnId\\\\\\\": \\\\\\\"$MONDAY_APPROVAL_COL_ID\\\\\\\"}\\\") { id board_id event } }\"}"
   ```

8. **Smoke test.** Send a test email to the triage inbox; within a minute
   you should see one Monday card land in the correct lane group, and either
   a Gmail draft (if `action: draft`) or a card sitting at `Awaiting Review`
   (if `escalate`).

---

## Running fixtures

The repo ships with 16 sample emails under `fixtures/` — 10 customer/vendor
emails (cases 1-10), 5 internal/leadership emails (internal_01…05), and 1
edge case (`edge_01_ach_meta_hybrid` — ACH language in the subject plus a
governance question in the body; money must always win). Each fixture has an
`expected_outcome` field showing what the chain should produce.

The chain shells out to the `openclaw` CLI, which lives **inside the bridge
container** — so run fixtures there, not on the host:

```bash
# Run all fixtures (inside the bridge container) and save each decision
docker compose exec bridge bash scripts/run_all_fixtures.sh

# Run a single fixture
docker compose exec bridge python3 bin/triage-chain.py \
    fixtures/case01.json /tmp/test-sops.json
```

`/tmp/test-sops.json` is the SOP catalog you'd normally fetch from Drive.
Build it once (inside the container) with:

```bash
python3 - <<'PY'
import json, pathlib, re
sops=[]
for d, status in [("sops/active","Active"),("sops/reference","Reference"),("sops/archived","Archived")]:
    for f in sorted(pathlib.Path(d).glob("*.md")):
        m=re.match(r'^((?:SOP|REF|ARCH)-\d{2})', f.name)
        sops.append({"id": m.group(1) if m else None, "name": f.name, "status": status, "content": f.read_text()})
pathlib.Path('/tmp/test-sops.json').write_text(json.dumps(sops))
PY
```

---

## Safety verification

### No-send proof

Run the audit script against the exported n8n workflow. This only greps the
JSON, so it runs fine on the host (no container needed):

```bash
bash scripts/verify_no_send.sh n8n/workflows/fitness-triage.workflow.json
```

Exit 0 = clean. Exit 1 = found a Send/Reply/SMTP/Forward node (must not exist).

### ACH early-exit proof

Send `fixtures/case06.json` through the chain. Verify the decision
JSON has:

- `primary_lane: "Finance / ACH / Owner Approval"`
- `action: "escalate"`
- `approver_role: "Owner"`
- `draft: null` (the chain does not draft a customer reply for vendor ACH)

Verify the resulting Monday card has `Approval = Awaiting Review` and a card
update body that flags the BEC risk in `internal_note`.

### Scope gate proof

Run any of the customer-facing fixtures (case01, case04, case08) through the
chain. Verify the decision JSON has `action: "out_of_scope"` and either
`scope_label: "gorgias_owned"` or `scope_label: "unknown"`. No Monday card,
no Gmail draft.

### Schema validation proof

Run the full fixture set (inside the bridge container) and confirm every
decision's `schema_errors` array is empty:

```bash
docker compose exec bridge bash scripts/run_all_fixtures.sh
docker compose exec bridge python3 -c "
import json, pathlib
errs = 0
for f in pathlib.Path('/tmp/runs').glob('*.decision.json'):
    d = json.loads(f.read_text())
    e = d.get('schema_errors') or []
    if e: print(f.name, e); errs += len(e)
print(f'total schema errors: {errs}')
"
```

---

## Operational notes

- **Audit logs** live in `out/req-*.decision.json` (per-request decision JSON)
  and `out/req-*.triage.err` (per-request chain stderr). Retention should be
  at least 90 days. Wipe with `rm out/req-*` between deployments if you don't
  want to carry sandbox history forward.
- **Monitoring stuck approvals**: query Monday for cards where Approval is
  still `Awaiting Review` after N hours. Add this as a periodic Monday
  automation or an external dashboard cron.
- **Adding a new SOP**: drop a new markdown file under `sops/active/` (or
  reference/archived) with the naming convention `SOP-NN_Short_Title.md`. The
  chain picks it up on the next request — no restart needed. SOPs are fetched
  fresh from Drive on every n8n run, so changes propagate immediately.
- **Adding a new test fixture**: write a JSON file under `fixtures/` with the
  same shape as `case01.json`. Add an `expected_outcome` block. Re-run
  `scripts/run_all_fixtures.sh` to verify.

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| Schema validation failures | Open the relevant `out/req-*.triage.err`. The first error names the field that failed and which skill produced it. Almost always a prompt issue, not a code issue. |
| OpenClaw not reachable | `docker compose ps` should show `openclaw` up. Check `docker compose logs openclaw` for the gateway "ready" line. The bridge reaches it on `127.0.0.1:18789` via host networking. |
| Bridge "triage failed" / 502 from the OpenClaw HTTP node | `docker compose logs bridge`. The chain shells out to the `openclaw` CLI per skill — confirm the bridge image built with the CLI (`docker compose exec bridge which openclaw`). A common cause is an expired/invalid `OPENAI_API_KEY` in `.env`. |
| `[bridge] create_item FAILED` from monday-card.sh | Check `MONDAY_API_TOKEN`, `MONDAY_BOARD_ID` in `.env`, and that `config/monday-groups.json` has an entry for the lane the chain returned. |
| Gmail draft never appears | n8n's Gmail Create Draft node usually shows the failure inline in the workflow execution view. Check that the Gmail credential is connected and has the `gmail.compose` scope. |
| Gmail OAuth callback fails | The authorized redirect URI on the Google Cloud Console OAuth client must include `https://<your-n8n-host>/rest/oauth2-credential/callback` exactly. |
| Monday card not created on a real email | The triage chain may have returned `action: out_of_scope`. Check the decision JSON in the `bridge_out` volume (`docker compose exec bridge cat /root/Arvin/out/req-<id>.decision.json`). If correct, the scope gate is correctly blocking; the email belongs to Gorgias. |
| Skill edit not taking effect | Skills are bind-mounted (`./skills` → container workspace), so edits are live with no restart. If a change isn't reflected, confirm you edited the repo copy under `./skills/`, not the old host workspace path. |
| n8n trigger not firing | Gmail Trigger polls every minute by default. If you're impatient, click "Execute Workflow" in n8n to fetch the next unread message immediately. |
| Same email creates two Monday cards | The idempotency check on `gmail_message_id` should prevent this. Verify the new card has the Gmail Message ID column populated; if not, check `MONDAY_GMAIL_MSGID_COL_ID` is set correctly. |

For deeper documentation see:

- `docs/ARCHITECTURE.md` — the system, in long form
- `docs/SAFETY.md` — the four-layer safety enforcement model
- `docs/DEPLOYMENT.md` — step-by-step setup, expanded
- `docs/TESTING.md` — fixture conventions + regression playbook
- `docs/MILESTONE_2_ACCESS.md` — what we need for production cutover
- `docs/GMAIL_INTERNAL_NOTES_SPIKE.md` — research result on the Gmail-notes
  feature mentioned in the original brief (with open question for the doc
  author)
