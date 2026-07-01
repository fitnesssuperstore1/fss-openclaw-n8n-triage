# Rollback Procedure

If this PR (#3) needs to be reverted after merge, the following restores the previous `main` state. This milestone is **code + config only** — no database or data migrations.

> ⚠️ **Note:** `main` @ `7df76d5` is the **pre-corrections** state. Rolling back re-introduces the exact issues this PR fixed (Slack in workflows, unpinned `:latest` images, no `N8N_ENCRYPTION_KEY`, publicly-bound ports, Drive-wide SOP search, etc.). Only roll back if the corrections themselves cause a problem; otherwise fix forward.

## Pre-merge information (record before merge)
- Pre-merge `main` SHA: **`7df76d5`**
- Merge commit SHA: *(fill in after merge)*
- Corrective PR: **#3**
- Deploy environment(s) affected: sandbox VPS (production cutover is Milestone 2)

## Standard rollback (on the deploy host)
1. `docker compose down` *(keeps the named volumes — n8n workflows/credentials persist)*
2. `git fetch origin`
3. `git checkout 7df76d5`
4. `docker compose build --no-cache`
5. `docker compose up -d`
6. Verify services: `docker compose ps` + health check — `curl -s http://127.0.0.1:8088/health` → `{"ok":true}`
7. Re-run the no-send safety check on every export (script takes one file at a time):
   ```
   for f in n8n/workflows/*.json; do bash scripts/verify_no_send.sh "$f"; done   # each must exit 0
   ```
8. Notify Izza + Arvin that rollback is complete, with the reason.

## Reverting the merge on GitHub (if rollback happens before deploy)
1. `git revert -m 1 <merge-commit-sha>` on `main` (no history rewrite)
2. Open a revert PR
3. Merge the revert PR
4. Redeploy from the reverted `main`

## No data migration
Code + config only — no database migrations, no SOP-data migrations, no persistent-state changes that require restoration.

## Configuration to preserve
- `.env` is **git-ignored** and lives only on the deploy host — a code rollback does **not** touch it.
- **Credentials survive the rollback:** n8n stores its credentials **and** the encryption key inside the `n8n_data` volume, which `docker compose down` does not remove. So connected credentials keep decrypting after a code-only rollback.
- New env vars introduced by this PR are safe to leave in `.env`:
  - `N8N_ENCRYPTION_KEY` (B9) — keep it. The stored key in the `n8n_data` volume is what actually decrypts credentials; leaving the var set (or relying on the volume) preserves them.
  - `SOP_ACTIVE_FOLDER_ID` / `SOP_ARCHIVED_FOLDER_ID` / `SOP_REFERENCE_FOLDER_ID` (B10) — harmless if left; the pre-PR Drive node simply ignores them.

## Post-rollback verification
- All services healthy (`docker compose ps`, health endpoint returns ok)
- Internal ports not publicly exposed (`ss -ltn` shows 8080/8088/18789 on 127.0.0.1) — note: the pre-PR compose may bind these more broadly, since loopback binding was part of this PR (B9)
- Fixture suite runs against the pre-PR code: `bash scripts/run_all_fixtures.sh`
- No orphaned Monday items or Gmail drafts created by the reverted code (the one-email-one-item idempotency by message-id still applies)
