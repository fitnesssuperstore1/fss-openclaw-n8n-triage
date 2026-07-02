# Milestone 2 — Required Access

Everything below must be granted at Milestone 2 kickoff for the production cutover. **Every item must be company-owned and rotatable — no personal credentials.** Env-var names match `.env.example` in this repo so each item can be cross-checked against the code.

## Gmail (Gmail Trigger + Create Draft nodes)
- **OAuth 2.0 client** — `client_id` + `client_secret` + `refresh_token` for the production inbox
  → `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`
- **Scopes (least-privilege):** `gmail.readonly` (trigger reads unread mail), `gmail.compose` (create drafts — the system **never sends**), `gmail.labels` (optional, if labeling)
- **Authorized redirect URI:** `https://<n8n-host>/rest/oauth2-credential/callback`
- **Inbox address:** the production internal/leadership inbox → `.env`: `GMAIL_USER` *(TBD by client)*

## Google Drive (SOP fetch — "Search files and folders" node)
- **OAuth 2.0 client** (same Google project) or a service account, scope **`drive.readonly`**
- **Restricted to the approved SOP folders only** (not Drive-wide) — the 3 folder IDs:
  → `.env`: `SOP_ACTIVE_FOLDER_ID`, `SOP_ARCHIVED_FOLDER_ID`, `SOP_REFERENCE_FOLDER_ID` *(IDs provided by client)*
- The Drive query is already scoped to these folders (B10); no broad access needed.

## Monday.com
- **API v2 token, board-scoped** → `.env`: `MONDAY_API_TOKEN`
- **Board ID** for the production CS Triage board → `.env`: `MONDAY_BOARD_ID`
- **Column IDs** on that board → `.env`: `MONDAY_APPROVAL_COL_ID` (the Approval/status column), `MONDAY_GMAIL_MSGID_COL_ID` (Gmail message-id column, used for one-email-one-item idempotency)
- **Lane → group map** → `config/monday-groups.json` (copied from the committed `config/monday-groups.example.json`)
- **Permissions:** read + write on items, columns, and item updates for **that board only**

## Model provider (OpenAI / Anthropic)
- **API key on the company billing account** → `.env`: `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`)
- **Model:** `.env`: `OPENCLAW_MODEL` (per-skill overrides available)
- **Rate limits** sized for ~5 model calls per inbound email × expected volume *(TBD)*

## n8n
- **Deployment host + company-controlled domain** → `.env`: `N8N_HOST`, `N8N_WEBHOOK_URL`
- **`N8N_ENCRYPTION_KEY`** — required, stable (generate `openssl rand -hex 24`); credentials break if it changes
- **Owner account** (n8n 2.x user management) → `.env`: `N8N_USER`, `N8N_PASSWORD`
- **Env via the company secret store, not the repo** (`.env` is git-ignored)
- Admin login for post-deploy sanity checks

## OpenClaw gateway
- **`OPENCLAW_GATEWAY_TOKEN`** (optional) if the Control UI is exposed; gateway binds loopback + token auth
- **`OPENCLAW_GATEWAY_PORT`** (default 18789, loopback-only)

## VPS / infrastructure
- Deploy host with **Docker + Docker Compose**
- **Public subdomain with valid TLS** (Traefik + Let's Encrypt) — company domain replaces the `example.com` placeholder
- **Firewall** restricting internal ports **8080 / 8088 / 18789 to loopback** (the stack already binds them to 127.0.0.1; a host firewall is the belt-and-suspenders)
- **SSH access for a non-root deploy user**

## Company-controlled placeholders currently in the repo (to replace at cutover)
- Traefik domain → `infra/traefik/traefik.yml` (ACME email) + `infra/traefik/dynamic/routes.yml` (`n8n.example.com` / `openclaw.example.com`)
- SOP folder IDs → `.env.example`: `SOP_*_FOLDER_ID` = `replace-me`
- Monday board/column IDs → `config/monday-groups.example.json` + `.env.example`
- `N8N_ENCRYPTION_KEY` → `.env.example`: `replace-me-with-a-32+char-random-string`

## Explicitly NOT required for Milestone 2
- **Shopify** access (Phase 2)
- **Gorgias** access (Phase 2)
- Any **personal credential** from the contractor
