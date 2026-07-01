# Milestone 1 Corrections — Evidence Sheet

Branch: `milestone-1-corrections` · PR: **#3** into `main` (not merged — for acceptance) · Base `main`: `7df76d5` · Final commit SHA: recorded in the PR description (branch tip).

Supporting output files referenced below live in this same `evidence/` folder.

| Criterion | Result | Command output / screenshot | Issue found | Corrective commit / PR | Retest result |
|---|---|---|---|---|---|
| A1 — Repo private + company-owned | PASS | `gh repo view` → visibility **PRIVATE**, owner `fitnesssuperstore1` | none | n/a | confirmed |
| A2 — Main-branch commit SHA recorded | PASS | `7df76d5e1ac726a7b91c52c38ba6ba23742fb1f2` | none | n/a | n/a |
| A3 — Original M1 PR + merge commit recorded | PASS | **PR #1**, merge commit `7df76d5` | none | n/a | n/a |
| A4 — main branch protected | SEE NOTES | repository **admin setting**, not code; not enabled at PR time | branch protection not enabled at PR time | n/a — PR pathway followed (branch + PR, no direct commits to main) | repo owner to enable independently |
| A5 — Gitleaks full-history scan | PASS | `evidence/gitleaks-report.json` | **0 leaks**; no `.env`/key/cert/secret ever committed | n/a — nothing to rotate | n/a |
| B1 — Slack removal | PASS | `evidence/verify-no-slack.txt` | Slack nodes/credentials/connections + a duplicate Slack workflow export present | `ab42a22` | PASS — 0 Slack hits across all exports |
| B2 — `verify_no_send.sh` mixed-case fix | PASS | `evidence/verify-no-send-output.txt` | script compared `operation.lower()` against camelCase banned ops → `sendAndWait`/`replyTo`/… slipped past | `d05a358` | PASS — exits 0 clean; mixed-case sends now caught |
| B3 — Workflow sanitization | PASS | `evidence/sanitization-verify.txt` | `pinData`/`staticData`/`meta.instanceId`/credential ids + a test email present | `afb376b` | PASS — 0 emails; valid JSON; imports clean |
| B4 — WF2 + `monday-groups.example` | PASS | `evidence/wf2-import.txt` | `monday-groups.example.json` missing; WF2 clean import unverified | `84a30a5` | PASS — "Successfully imported 2 workflows" |
| B5 — Prompt-injection guard + size cap | PASS | `evidence/prompt-injection-test.txt` | untrusted email body fed straight into the prompt; no size cap | `a47330b`, `1fedf0e` | PASS — nonce-delimited data block + 512 KB/50k caps |
| B6 — Bridge temp files + response leakage | PASS | `evidence/bridge-cleanup-verify.txt` | predictable `/tmp/req-*` never cleaned; `pipeline_log`/stderr returned in responses | `a47330b` | PASS — mkstemp 0600 + finally cleanup; decision-only responses |
| B7 — Fixture runner correctness | PASS | `evidence/fixture-suite-output.txt` | missing `expected_outcome`/`expected_lane` silently passed | `de23e28` | PASS — hard-fails on missing/skipped expectations; asserts `expected_lane` |
| B8 — Awaiting Review stamping | PASS | `evidence/monday-status.txt` | status stamped on `draft_pending_approval` only, not escalate/ACH/Owner | `d17e2b0` | PASS — stamped for escalate/ACH/Owner + approval-required |
| B9 — Versions / auth / ports / domain | PASS | `evidence/versions-and-ports.txt` | `:latest`/unpinned; no `N8N_ENCRYPTION_KEY`; contractor domain; services on public interfaces | `03ad509` | PASS — node 22.22.3 / openclaw 2026.6.5 / traefik 3.2.5 / n8n 2.21.7 pinned; enc key set; loopback binds; company-domain placeholder |
| B10 — Drive SOP scope | PASS | `evidence/drive-scope.txt` | Drive-wide search by filename prefix | `5410e41` | PASS — scoped to 3 approved folders via `$env.SOP_*_FOLDER_ID` |
| B11 — Timeout alignment + idempotent retry | PASS | `evidence/timeout-verify.txt` | per-skill 210s vs bridge 240s; duplicate side-effects on retry | `d952201` | PASS — layered 120<600<700<760s; 504 on timeout; no-retry + msgid dedup |
| C — Clean-clone runtime verification (self-run) | PASS (pending Izza's independent VPS run) | `evidence/clean-clone-run.txt` | 4 issues surfaced during the self-run (see commits →) | `33d212e`, `865b7b7`, `f935c02`, `2edfcd3` | PASS — build + `up -d` + health; ports 8080/8088/18789 loopback; ACH→`draft=null`; customer→out_of_scope; fixture suite green |

**Notes**
- **A4** — branch protection is a GitHub repo-admin setting, not something implementable in this PR. The corrective work complies with the intent (authored on `milestone-1-corrections`, delivered via PR #3, no direct commits to `main`). The repo owner should enable protection rules independently.
- **C** — self-verified end-to-end on a clean, disposable server (built fresh from this branch, then torn down). Izza's independent VPS run is the acceptance gate; outputs in `evidence/clean-clone-run.txt` are the actual self-run results for comparison.
- Every result above is from an actual run. Where a result is not a clean PASS, it is marked **SEE NOTES** rather than a faked PASS.
