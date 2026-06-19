# Deployment

This is the long form of the README's "Quick start". A reader who has never
seen this project should be able to follow this from a fresh server to a
working sandbox without asking.

If you only need the abbreviated version, the README's `## Quick start`
section is enough. Use this doc when something in that quick start doesn't
behave the way you expected.

---

## Prerequisites in detail

### Host

- Linux server (tested on Ubuntu 24.04). 4 GB RAM minimum, 2 GB free disk.
- A user account that owns the project directory. The user must be in the
  `docker` group (`sudo usermod -aG docker $USER` if not).
- `jq`, `curl`, `python3` (3.11+), `git` installed on the host. The bash
  scripts in `bin/` use jq to build GraphQL payloads.

### Network

- A public IPv4. Cloud providers like Netcup, Hetzner, DigitalOcean all
  work; the only requirement is the box can serve ports 80 and 443.
- Two DNS A records pointing at the box, e.g. `n8n.example.com` and
  `openclaw.example.com`. Wait for DNS to propagate before starting Traefik
  (Let's Encrypt's HTTP-01 challenge needs the hostname to resolve).
- Ports 80 and 443 open in any provider-level firewall.

### Accounts

- **OpenAI** project + API key, with enough quota for ~5 calls per inbound
  email. The drafting + audit skills use a stronger model; the bounded
  classification skills can use a cheaper one. Set the project's monthly
  cap so a runaway loop cannot bill catastrophically.
- **Google Cloud project** with the OAuth consent screen configured and
  the Gmail + Drive APIs enabled. Create an OAuth 2.0 Client ID of type
  "Web application". Add `https://n8n.<your-host>/rest/oauth2-credential/callback`
  to the Authorized redirect URIs. Save the Client ID, Client Secret.
- **Google Workspace user** whose Gmail inbox will be the triage target,
  with Gmail + Drive access. You'll OAuth this account from inside n8n.
- **Monday.com workspace**. Generate an API token (Profile → Developers →
  My access tokens → Show). Create a board called `CS Triage` with 8 groups
  matching the 8 workflow lanes (names exactly as in
  `config/monday-groups.example.json`).
- **OpenClaw**: nothing to install on the host. It runs as a compose service
  built from `openclaw/Dockerfile` (which `npm install -g openclaw` inside
  the image). The same image backs the `bridge` service so the chain's
  `openclaw agent --local` calls work there too.

---

## Step-by-step setup

### 1. Clone the repo

```bash
git clone <repo-url> ~/fitness-superstore-triage
cd ~/fitness-superstore-triage
```

### 2. Lay down the secrets directory

```bash
mkdir -p ~/secrets
chmod 700 ~/secrets

# OpenAI
printf '%s' '<your sk-proj-...>' > ~/secrets/openai.key
chmod 600 ~/secrets/openai.key

# Monday
printf '%s' '<your eyJhbGc...>' > ~/secrets/monday.key
chmod 600 ~/secrets/monday.key

# (Optional) Anthropic, if you'll fall back to Claude
# printf '%s' '<your sk-ant-...>' > ~/secrets/anthropic.key
# chmod 600 ~/secrets/anthropic.key
```

**Tip:** type the keys, never paste them via chat or screen share. If a key
ever appears in a transcript, OpenAI / Monday will eventually auto-revoke it
and you'll need to rotate.

### 3. Copy and fill the env files

```bash
cp .env.example .env
cp config/env.sh.example config/env.sh

$EDITOR .env
$EDITOR config/env.sh
```

Both files reference the same logical values; `.env` is read by Docker
(n8n, Traefik, the bridge container), and `config/env.sh` is read by the
bash scripts inside the bridge. Keep them in sync.

The values you must fill before anything works:

- `OPENAI_API_KEY` — sk-proj-...
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — from the OAuth client
- `MONDAY_API_TOKEN` — eyJhbGc...
- `MONDAY_BOARD_ID` — number after `/boards/` in the Monday URL
- `MONDAY_APPROVAL_COL_ID`, `MONDAY_GMAIL_MSGID_COL_ID` — see step 5
- `N8N_HOST`, `N8N_WEBHOOK_URL` — your DNS names
- `N8N_USER`, `N8N_PASSWORD` — for n8n's basic auth
- `GMAIL_USER` — the triage inbox address

### 4. OpenClaw — nothing to install on the host

OpenClaw runs as a compose service, not a host process. The image
(`openclaw/Dockerfile`) does `npm install -g openclaw`, and the
`openclaw/entrypoint.sh` startup script registers the OpenAI key from the
`OPENAI_API_KEY` env var (set in `.env`) into the agent auth-profile before
starting the gateway. The same image backs the `bridge` service, so the
chain's `openclaw agent --local` skill calls work inside the bridge too.

So there's no `npm install`, no systemd unit, no manual auth-profile edit.
Skills are bind-mounted from `./skills` (see the compose file), so editing a
`SKILL.md` on the host is live in the containers with no rebuild.

Just make sure `OPENAI_API_KEY` is set in `.env` (step 3) — the entrypoint
handles the rest at `docker compose up`.

### 5. Provision the Monday board structure

In the Monday UI, on the CS Triage board:

- Create 8 groups, one per workflow lane:
  - New Orders / Pending Shipments
  - Shipping CS
  - Parcel / Small Package
  - Install / Service / Warranty
  - Sales CS
  - Finance / ACH / Owner Approval
  - Product Content / Ecommerce
  - Escalate / Needs Human Review
- Create a **Status** column called `Approval` with labels:
  `Awaiting Review`, `Approved`, `Rejected`, `Draft Ready`, `Sent`.
  Note its `id` from the API: `query { boards(ids: <BOARD_ID>) { columns { id title type } } }`.
- Create a **Text** column called `Gmail Message ID`. Note its `id` the
  same way.

Record both column IDs in `.env` (`MONDAY_APPROVAL_COL_ID`,
`MONDAY_GMAIL_MSGID_COL_ID`).

Build `config/monday-groups.json` as a flat lane → group id map. The 8 group
ids are easiest to grab via:

```bash
TOKEN=$(cat ~/secrets/monday.key)
curl -s https://api.monday.com/v2 \
  -H "Authorization: $TOKEN" -H "Content-Type: application/json" -H "API-Version: 2024-10" \
  -d '{"query":"query{ boards(ids:<BOARD_ID>){ groups{ id title } } }"}'
```

Save the result into `config/monday-groups.json`.

### 6. Bring up the stack

```bash
docker compose pull
docker compose up -d
docker compose logs -f --tail=80
```

Watch for:

- `traefik` reuses the existing certs in `infra/traefik/letsencrypt/`; on a
  fresh host it issues new ones via the Let's Encrypt HTTP-01 challenge
  (~1 min). It serves both subdomains over HTTPS.
- `openclaw` should log `[entrypoint] starting gateway on :18789` then
  `[gateway] ready`.
- `n8n-import` runs once and exits — log shows either the import of each
  workflow or `workflows exist, skipping import`.
- `n8n` should log "Editor is now accessible via: https://<your-n8n-host>".
- `bridge` should log `[bridge-entrypoint] starting triage-server.py on :8088`.

### 7. Configure n8n credentials

Open `https://n8n.<your-host>/`, log in with the basic-auth user from
step 3.

For each external system, click **Credentials → New** and create:

- **Gmail OAuth2** — paste in the Client ID and Client Secret, then click
  Connect to OAuth the triage account.
- **Google Drive OAuth2** — same Client ID/Secret as Gmail (Google scopes
  cover both).
- **Monday.com API** — paste the Monday API token.
- **HTTP Header Auth** (for the WF2 Monday calls) — name it `Monday API`,
  Header Name `Authorization`, Header Value the same Monday API token (no
  "Bearer" prefix; Monday accepts the raw token).

### 8. Re-map credentials on the workflows

The workflows are already in n8n — the one-shot `n8n-import` service seeded
everything in `n8n/workflows/` at first boot (it skips on later restarts, so
it never duplicates or overwrites). You do NOT import them by hand.

What you DO need: open each workflow and re-map every node's credential to the
ones you created in step 7 (the credential references in the seeded JSON are
placeholders the import can't resolve). Then activate both workflows.

### 9. Subscribe Monday's webhook to WF2

Get the production webhook URL from WF2's Webhook node. Then:

```bash
TOKEN=$(cat ~/secrets/monday.key)
BOARD=$(grep MONDAY_BOARD_ID .env | cut -d= -f2)
COL=$(grep MONDAY_APPROVAL_COL_ID .env | cut -d= -f2)
URL="<wf2-prod-url>"

python3 - <<PY
import json, urllib.request
token = "$TOKEN"
import json
cfg = json.dumps({"columnId": "$COL"})
q = (
    "mutation { create_webhook("
    f"board_id: $BOARD, "
    "event: change_specific_column_value, "
    f'url: \"$URL\", '
    f"config: " + json.dumps(cfg) + ""
    ") { id board_id event } }"
)
body = json.dumps({"query": q}).encode()
req = urllib.request.Request("https://api.monday.com/v2",
    data=body,
    headers={"Authorization": token, "Content-Type": "application/json", "API-Version": "2024-10"})
r = json.loads(urllib.request.urlopen(req).read())
print(json.dumps(r, indent=2))
PY
```

Monday will send a one-time challenge handshake to the URL during
subscription; WF2's Webhook node handles it automatically (the challenge
branch echoes the token back).

### 10. Smoke test

Send a test email from any other Gmail to your triage inbox. Within a
minute:

- The Gmail Trigger picks it up.
- A new card lands on the Monday board in the correct lane group.
- For `action: draft` — a draft appears in the triage inbox's Drafts
  folder, threaded onto the original conversation.
- For `action: escalate` — the card sits with Approval = Awaiting Review.
  Click the column on the card and pick Approved; within seconds, a Gmail
  draft appears in Drafts and the column flips to Draft Ready.

If none of this happens, walk through `docs/SAFETY.md`'s "How to verify
yourself" sections to figure out which layer broke down.

---

## Troubleshooting (deployment-specific)

| Symptom | Likely cause | Fix |
|---|---|---|
| Traefik logs `acme: unable to obtain certificate` | DNS not propagated yet | wait 5–15 min, restart traefik |
| n8n editor 502 from the public URL | Traefik can't reach n8n's port | check `N8N_PORT` matches what n8n is binding |
| `docker compose up` fails on `network_mode: host` | Docker rootless mode doesn't support host networking | use rootful Docker, or refactor to bridge networking (loses the OpenClaw localhost reachability) |
| `triage-server.py` exits immediately | missing `jsonschema` package in the container | already installed by the `pip install` in compose `command:`; check the bridge logs for the actual error |
| Bridge: `MONDAY_BOARD_ID: set MONDAY_BOARD_ID` | `config/env.sh` not sourced | the bash scripts source `config/env.sh` at the top; verify it exists and has `export MONDAY_BOARD_ID=...` |
| Monday cards never have the Gmail Message ID column set | the column id is wrong, or the column isn't of type `text` | re-query `boards(...){columns{id title type}}` and verify the id |
| All emails get blocked at scope_gate | scope_gate's "internal" inbox heuristics don't recognize your inbox addresses | edit `~/.openclaw/workspace/skills/scope_gate/SKILL.md` to add your real internal-inbox names to rules 2 and 3 |
| OpenAI key returns 401 invalid_api_key | OpenAI secret scanner auto-revoked it because it was leaked publicly | rotate the key; do not paste keys into chat or screen-share |
| OpenAI key returns 429 insufficient_quota | account out of credit | top up billing |

---

## Production cutover (not Milestone 1)

When the time comes (Milestone 2), see `docs/MILESTONE_2_ACCESS.md` for the
full access list and the controlled-cutover plan. The short version:

- Replace the sandbox Gmail, Drive folder, Monday board, and OpenAI key with
  the real production equivalents.
- Migrate `config/monday-groups.json` and the column IDs in `.env` to point
  at the real Monday board.
- Run a controlled period with the first N emails reviewed manually before
  relaxing oversight.
- Set up monitoring on Slack approval latency, schema_errors[], OpenAI
  spend.

Do not perform any of the above during Milestone 1. The whole milestone is
sandbox-only.
