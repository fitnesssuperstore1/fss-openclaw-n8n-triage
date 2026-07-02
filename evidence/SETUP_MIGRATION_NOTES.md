# Setup / Migration Notes — Milestone 1 Corrections PR

What a deployer of the `milestone-1-corrections` branch needs to know that differs from the previous `main`. This is code + config only — **no database migrations**.

## New environment variables (required)
Both are documented in `.env.example`:
- **`N8N_ENCRYPTION_KEY`** (B9) — required and must stay stable. Generate `openssl rand -hex 24`. n8n uses it to encrypt stored credentials; if it changes after credentials are connected, they stop decrypting.
- **`SOP_ACTIVE_FOLDER_ID` / `SOP_ARCHIVED_FOLDER_ID` / `SOP_REFERENCE_FOLDER_ID`** (B10) — required. The Drive "Search files and folders" node scopes SOP search to exactly these 3 approved folders; without them it returns nothing (fails closed, does not fall back to a Drive-wide search).

Optional: `OPENCLAW_GATEWAY_TOKEN` (gateway token auth, if the Control UI is exposed).

## Changed variable
- **`N8N_PORT` standardized to `8080`** in `.env.example` (previously mismatched at 5678 while Traefik + compose used 8080). Keep it at 8080 unless you change the Traefik route and compose together.

## New config file
- **`config/monday-groups.example.json`** — copy to `config/monday-groups.json` and populate with this environment's Monday group IDs. The real file is git-ignored (no real IDs committed).

## Version pins (B9) — rebuild required
docker-compose / Dockerfile now pin exact versions:
- Node **22.22.3**, OpenClaw **2026.6.5**, Traefik **3.2.5**, n8n **2.21.7**

Rebuild so the pins take effect on first deploy:
```
docker compose build --no-cache
```

## Port binding change (B9)
Internal services now bind **loopback only** (n8n `127.0.0.1:8080`, bridge `127.0.0.1:8088`, OpenClaw gateway `127.0.0.1:18789`). External access is via Traefik on 80/443. If you were hitting the internal ports directly during development, that no longer works — go through Traefik.

## Domain (B9)
Traefik ships `example.com` placeholders. Set your company domain in:
- `infra/traefik/traefik.yml` (ACME email)
- `infra/traefik/dynamic/routes.yml` (the two `Host(...)` rules)

## Workflow seeding (automatic — not a manual re-import)
The `n8n-import` service seeds `n8n/workflows/*.json` on first `up` (guarded by a marker file — imports once, skips on restart). The exports were re-sanitized after Slack removal (B1/B3) and ship **credential-less** (credential `id` blank, name `REPLACE_ME`). After first boot, **connect Gmail / Drive / Monday credentials in the n8n UI** and select them on the nodes. Create the n8n owner account on first login (n8n 2.x user management).

## No database schema changes
No migrations. Code + config only.

## Order of operations
1. Pull the `milestone-1-corrections` branch
2. `cp .env.example .env` and fill required values (`N8N_ENCRYPTION_KEY`, the 3 `SOP_*_FOLDER_ID`, Monday IDs, Google OAuth, model key)
3. `cp config/monday-groups.example.json config/monday-groups.json` and populate real group IDs
4. Set the real domain in `infra/traefik/traefik.yml` + `infra/traefik/dynamic/routes.yml`
5. `docker compose down` (if a previous version is running)
6. `docker compose build --no-cache`
7. `docker compose up -d`  *(n8n-import seeds the workflows automatically)*
8. Verify health: `docker compose ps` + `curl -s http://127.0.0.1:8088/health` → `{"ok":true}`
9. Connect Gmail / Drive / Monday credentials in the n8n UI; create the n8n owner account
10. Fixture suite: `bash scripts/run_all_fixtures.sh`
11. No-send check: `for f in n8n/workflows/*.json; do bash scripts/verify_no_send.sh "$f"; done`  *(each exits 0)*
