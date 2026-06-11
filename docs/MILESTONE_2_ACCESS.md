# Milestone 2 — Production Access Requirements

This is the list of access we will need to move the triage system from the
sandbox we built in Milestone 1 to a controlled production deployment.
**Nothing on this list has been requested.** Milestone 1 is sandbox-only;
production access is the first deliverable of Milestone 2.

The list is intended to be handed to the client's IT / ops lead so they can
provision everything in parallel. The doc author may want to add
client-specific notes (compliance owner, security review track, named
approvers) before the request goes out.

---

## What we need, per system

### 1. Real customer-facing Gmail inbox

- **What:** the triage Gmail inbox where production email lands.
- **Why:** the Gmail Trigger in n8n needs to poll a real inbox; the Drafts
  folder needs to hold the holding-drafts the system produces.
- **Scope requested:**
  - `gmail.readonly` on the trigger inbox (so n8n can read incoming email)
  - `gmail.compose` on the same inbox (so n8n can create — but never send —
    drafts)
  - Nothing else. Explicitly NOT `gmail.send`, NOT `gmail.modify` beyond
    label changes, NOT `gmail.metadata` only.
- **Who provisions:** the Google Workspace admin
- **Auth method:** OAuth 2.0 via the Google Cloud project already created
  in step 2 below
- **Verification:** before production cutover, the safety audit script must
  confirm no `gmail.send` scope is present on any active credential.

### 2. Google Cloud project + OAuth 2.0 client

- **What:** a Google Cloud project that owns the OAuth client n8n uses to
  reach Gmail + Drive.
- **Why:** OAuth verification is the only way Google will allow n8n to
  read the production inbox.
- **Scope requested:** create / own; the project hosts the OAuth client
  ID and secret, the consent screen branding (Fitness Superstore
  branding, privacy policy URL, terms URL), and the OAuth verification
  status.
- **Authorized redirect URIs to register:** `https://<prod-n8n-host>/rest/oauth2-credential/callback`
- **Verification status:** OAuth verification for `gmail.compose` scope is
  required (this is the scope that's not in the basic set; Google reviews
  it before a Workspace can use it for an external app).
- **Who provisions:** Google Workspace admin / IT
- **Lead time:** OAuth verification typically takes 4-6 weeks. Start early.

### 3. Google Drive folder for the SOP catalog

- **What:** a Drive folder hosting the live SOP markdown files.
- **Why:** the current SOP source is `~/Arvin/sops/` on the sandbox host;
  production reads SOPs fresh from Drive on every triage run.
- **Folder structure expected:**

  ```
  Fitness Superstore SOPs/
  ├── Active/
  │   ├── SOP-01_…md
  │   ├── SOP-02_…md
  │   └── …
  ├── Reference/
  │   └── REF-01_…md
  └── Archived/
      └── ARCH-01_…md
  ```

- **Scope requested:** `drive.readonly` on this folder only (use a shared
  drive or a service-account scoped to it).
- **Who provisions:** SOP owner (currently TBD; ask Eaunic). Recommend the
  SOP owner stay the authoritative writer of the live SOPs after cutover.
- **Verification:** the n8n Drive Search node, when scoped to this folder,
  must return ~12 entries.

### 4. Monday.com production board

- **What:** the real CS Triage board the production triage system writes
  to. Distinct from the sandbox board we used during Milestone 1.
- **Why:** the sandbox board has demo data and our test cards. Production
  needs a clean board that the CS team will actually use.
- **Structure to provision:**
  - 8 groups, one per workflow lane (names exactly as in
    `config/monday-groups.json`)
  - Approval status column (5 labels: Awaiting Review / Approved /
    Rejected / Draft Ready / Sent)
  - Gmail Message ID text column (for idempotency)
  - Person column (the assigned approver)
  - Date column (creation date / due date)
- **API access:** a Monday API token from a service user dedicated to the
  triage system (not a personal token). Scope: write access to this board
  only.
- **Webhook permission:** the service user must be able to create webhooks
  on this board (for WF2 subscription).
- **Who provisions:** Monday workspace admin + the CS Lead
- **Verification:** before cutover, confirm the column IDs in production
  `.env` match the real board.

### 5. OpenAI / Anthropic API key on the client's billing account

- **What:** a production API key on the client's OpenAI (or Anthropic)
  account, not on any of our personal accounts.
- **Why:** all spend should be on the client's billing. Our personal-account
  keys had quota issues during sandbox testing; we don't want that for
  production.
- **Scope requested:** a project-scoped API key (sk-proj-...) with
  - read+write on the chat completions endpoint
  - a monthly spending cap that matches projected volume (recommend
    starting at $50/month for the first 30 days, then re-evaluate)
  - alerts to the on-call email at 50%, 80%, 100% of the cap
- **Who provisions:** finance / accounting (to attach billing) + the dev
  setting up the API project
- **Verification:** the key returns HTTP 200 from `/v1/chat/completions`
  with a small test prompt, and `/v1/models` lists the models we plan to
  use.

### 6. Slack workspace and dedicated approver channel

- **What:** if Slack is reintroduced for any approval flow in Phase 2 (it
  was removed in Milestone 1 per the rule set), a dedicated channel and a
  Slack app.
- **Why:** optional for Phase 2; for Milestone 1 / Milestone 2 cutover,
  Slack stays removed and approvals are Monday-only.
- **If needed later:**
  - One channel, e.g. `#triage-approvals`
  - Slack app with scopes: `chat:write`, `chat:write.public`,
    `channels:read`, `users:read`
  - Bot user invited to the approver channel
- **Who provisions:** Slack workspace admin

### 7. Compute / hosting (n8n, OpenClaw, bridge)

- **What:** the production server stack. Same shape as the sandbox.
- **Recommended sizing:** 4 vCPU, 8 GB RAM, 40 GB disk. The bridge is
  Python (light), n8n is Node (moderate), Traefik handles TLS termination.
  OpenClaw uses moderate memory.
- **Network:** public IP + two DNS subdomains (`n8n.<prod-host>`,
  `openclaw.<prod-host>`) with A records.
- **Firewall:** 80 + 443 open inbound; 22 SSH from admin IP only.
- **Who provisions:** ops / infra. Recommend a managed VPS (Hetzner /
  DigitalOcean / Netcup work fine; the sandbox runs on Netcup).
- **Backups:** scheduled snapshot of the n8n Docker volume daily.

### 8. Named approver identities

- **What:** the people who hold the `CS Lead`, `Ops Manager`, and `Owner`
  approver roles. The chain hard-codes these labels into every escalate
  decision; we need to know who each label maps to in production.
- **Why:** the Monday card's Person column is set to the approver; when
  Approval is flipped to Awaiting Review, that person needs a Monday
  notification rule pointing at their account.
- **Who provisions:** the operations / CS leadership team. Names go into
  Monday automation rules (e.g. "when Approval = Awaiting Review and
  Approver role = Owner, notify @<owner-handle>").

### 9. Compliance / security review

- **What:** sign-off from Legal + Security before any real customer email
  passes through the system.
- **Why:** PII handling. Even though Phase 1 only triages internal/
  leadership email (no customer PII), the moment we expand scope or
  include any Gorgias-side email, customer data is in the pipeline.
- **Recommended scope:**
  - Confirm log retention policy meets the client's compliance window.
  - Confirm OpenAI's data usage terms are acceptable (zero data
    retention if needed).
  - Confirm Monday's data residency (US vs EU) matches the client's
    requirements.
- **Who:** Legal + Security
- **Lead time:** internal review; varies.

---

## Recommended cutover sequence

1. **All of the above provisioned** (parallelisable except the OAuth
   verification, which is the long pole).
2. **Mirror everything to the production server**: same Docker stack, same
   skill files, same schemas; only the `.env` / `config/env.sh` differ.
3. **Soft-launch on a parallel inbox** that mirrors production traffic to
   a separate Gmail account for the first week. Compare the chain's
   decisions side-by-side with how the team would have handled each email
   manually.
4. **Cutover the real triage inbox** to point at the production system.
   For the first ~20 emails, every Monday card is manually reviewed by
   the CS Lead before any draft moves to Approved.
5. **Relax oversight gradually** once the soft-launch + first-20 review
   shows consistent behaviour.
6. **Set up monitoring** for:
   - Slack/Monday approval latency (avg time from Awaiting Review to
     Approved)
   - Schema error rate (`schema_errors` non-empty rate)
   - OpenAI spend vs cap (alert at 80%)
   - Per-day count of `action: out_of_scope` (a spike means scope_gate is
     mis-classifying or the team is mis-routing email)

---

## Things explicitly NOT needed for Milestone 1

To avoid confusion: in Milestone 1, do NOT request, configure, or use:

- The real customer-facing Gmail inbox
- The production Drive SOP folder
- The production Monday board
- The client's OpenAI billing account
- Slack
- A production Cloud project's OAuth verification

Milestone 1 is sandbox-only. The whole point of this list is to start the
provisioning ball rolling at the END of Milestone 1, so Milestone 2 doesn't
get stuck waiting on access reviews.
