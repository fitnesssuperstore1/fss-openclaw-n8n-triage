# Known Limitations — Milestone 1

These are honest, known limitations of the Milestone 1 system as delivered. None is a correctness defect; each is either expected safety behavior or a Milestone 2 item.

## Idempotency and duplicate prevention
- The one-email-one-item guarantee relies on the Gmail `message_id` dedup check in `monday-card.sh`, which queries current Monday board state before creating an item. If Monday is unreachable or times out at exactly the wrong moment, a duplicate item could theoretically be created; the next successful run would surface it. Not a data-loss risk, but requires operator awareness. (Requires `MONDAY_GMAIL_MSGID_COL_ID` configured — without it, the dedup check is skipped.)

## Failure-mode behavior (fail-closed)
- **Infrastructure failure (OpenClaw / model provider unreachable):** the skill call raises and the chain **exits with an error — no draft and no Monday item are created** (fail-closed; it never guesses). The failure surfaces in the per-request pipeline error log and the bridge returns a 5xx to n8n for retry. It does **not** silently produce a customer-facing action.
- **Skill schema-validation failure (malformed model output):** this **does** resolve gracefully — the chain force-escalates with a `schema_errors` entry (or returns `out_of_scope` if the failure is at the scope gate — the safe default).
- **No automated alerting** on a `schema_errors` / error backlog. A high error rate only surfaces via the audit log or n8n execution history. Alerting is a Phase 2 candidate.

## Scope gate
- The scope gate classifies in/out of scope from the configured company inbox rules and is **defensive** — unknown senders/inboxes default to **out of scope**. This can reject some legitimate internal emails as false positives. Precise internal/leadership signal definitions await client input; refinement is a Milestone 2 setup task.

## SOP source
- The SOP layer is abstracted behind a `SopSource` interface (`bin/sop_source.py`). The wired implementation is **`InMemorySopSource`**, fed by the SOPs the n8n workflow fetches from the approved Drive folders. **`IndexSopSource` is a Milestone 2 stub** (raises NotImplemented) for the production SOP Index / RAG system — expected, since the production Index metadata shape is TBD.

## Timeouts and long-running skills
- The aligned timeout budget (per-skill 90s → chain 600s → bridge 700s → n8n 760s) assumes the model provider responds within the per-skill budget. An extreme outlier (a single skill exceeding ~90s) times out and the email **fails closed** (errors, no wrong action) rather than drafting on incomplete reasoning. This is expected safety behavior.

## Testing coverage
- The 16-fixture regression suite (10 brief cases + internal/leadership + edge cases) passes with **zero schema errors** and no skipped assertions. Cases **outside** these fixtures — multipart / HTML-only emails, unusually large attachments, non-English content — are not explicitly covered. Recommended for Phase 2 expansion.

## What is NOT a limitation
- **No known bypass of the no-send guarantee** — the workflow contains only a Gmail *Create Draft* node (no send/reply/forward), structurally enforced and checked by `verify_no_send.sh`.
- **No known bypass of the ACH escalation** — a hardcoded skill rule plus an early-exit branch in the chain (`Finance / ACH / Owner Approval` → escalate to Owner, `draft=null`).
- **No known bypass of the archive-conflict rule** — Active SOPs control drafting; archived SOPs are only noted as a flagged conflict, never used to draft.
