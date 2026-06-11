# Spike: Gmail "Internal Notes" on Drafts

**Status:** research / spike — no code written yet.
**Open question for the doc author (Eaunic / Arvin):** see "Recommendation" below.

## What the milestone doc asks for

From `MILESTONE_1.md` §2.2:

> **Gmail internal notes** — inline reviewer comments on the draft itself
> (Gmail's feature where notes can be attached to a draft without being visible
> to the customer)

The doc treats this as an existing Gmail feature that we can call via API and
use as a second approval surface alongside Monday.

## What Gmail's API actually exposes for drafts

Gmail's REST API (v1) handles drafts through these endpoints:

- `users.drafts.create / get / list / update / delete / send` — manage the
  draft's body, subject, attachments, recipients
- `users.drafts.send` — sends the draft (we MUST NOT call this in Phase 1)
- `users.messages.modify` — can add/remove labels on the underlying message
  (drafts also have an associated message)

**There is no first-class "draft note" or "draft annotation" field** in the
public Gmail API. The Draft resource shape is essentially `{ id, message }` —
no `notes`, `comments`, or `reviewer_notes` field exists.

## What the doc author is probably thinking of (best guess)

A few real things people sometimes call "internal notes on a Gmail draft":

1. **Comments in Google Workspace drafts (Smart Compose / @-mention comments).**
   Workspace administrators can enable a comment feature on drafts, similar to
   Google Docs comments. This is **a Workspace UI feature**, not a Gmail API
   primitive — there is no public API for reading/writing these comments
   programmatically.

2. **Labels as a poor-man's note channel.** Reviewers apply labels like
   `approved`, `rewrite-paragraph-2`, `hold` to the draft's underlying message.
   The `users.messages.modify` endpoint can read/write labels via API. This is
   workable but is just a flat tag, not free-text commentary.

3. **A "review" comment posted as a separate adjacent Gmail thread.** The
   reviewer replies to the original customer email in a new thread visible only
   to the team (e.g. by changing the `To:` to an internal address). API-callable
   but creates a parallel conversation rather than "notes on the draft."

4. **A custom convention inside the draft body itself.** Wrap reviewer
   commentary in `<!-- internal: ... -->` HTML comments or a `[INTERNAL]`
   section that's stripped before send. The draft owns the note, but anyone
   with edit access to the draft can see / change it.

## Recommendation

Before writing any code, **ask Eaunic / Arvin what they mean by "Gmail internal
notes"**. The answer changes the implementation completely:

- If they mean **Workspace UI draft-comments** → there is no public API; we
  cannot read or write these programmatically. We'd have to drop this from
  Milestone 1 and document it as a manual-only channel.
- If they mean **labels as flags** → we use `users.messages.modify` with a small
  vocabulary of `approval/*` labels (e.g. `approval/approved`,
  `approval/rewrite`, `approval/hold`). Implementable in ~half a day.
- If they mean **a header section in the draft body** → we add it via
  `users.drafts.update`, and the bridge strips it before any send (which is
  impossible anyway because we never send). Trivial.
- If they mean **a separate internal-only adjacent thread** → we use
  `users.drafts.create` with the internal team as `To:` and link it to the
  customer draft via a custom header / thread id. Implementable in ~1 day.

## Suggested message to send back

> "Quick question on the Gmail internal notes feature in §2.2 — Gmail's public
> REST API doesn't expose a notes/comments field on the Draft resource. Did you
> mean (a) Workspace UI draft-comments, (b) labels as flags, (c) a header
> section in the draft body, or (d) something else? The implementation differs
> substantially per option."

## Confirmation via web search (June 2026)

A quick web search confirms Gmail does not have a native internal-notes
feature. What people commonly call "Gmail internal notes" is always one of
the following third-party tools or workarounds:

- **Gmelius** — Chrome extension adding a side panel with notes, @mentions,
  and a real API; widely used in business support workflows.
- **Streak** — CRM overlay with note functionality on threads.
- **Simple Gmail Notes** — free Chrome extension; notes stored in Drive.
- **Labels as flags** — apply approval labels (e.g. `approval/approved`,
  `approval/rewrite`, `approval/hold`) via `users.messages.modify`. Native
  Gmail API, no extension needed.
- **A separate internal thread / drafts as note storage / Google Keep / Chat**
  — manual workarounds that don't really integrate with the customer-facing
  thread.

So the sharper question to send the doc author is:

> "Which of these did you mean — Gmelius, Streak, Simple Gmail Notes, labels
> as flags via the Gmail API, or something else? Each has a different (or no)
> API and the implementation differs substantially.
>
> - If Gmelius: real API exists, ~half a day of work.
> - If labels: cheapest; uses Gmail's `messages.modify` to apply
>   `approval/*` labels.
> - If Workspace UI draft-comments: no public API; we'd have to drop this
>   from Milestone 1 as 'manual channel only'.
> - If something else: tell us which tool and we can scope it."

## Action while we wait for clarification

For Phase 1 / Milestone 1, the **Monday card update body is already serving
as the primary internal-review surface** (the `[PROPOSED DRAFT]` section we
added in `monday-card.sh` carries the draft for the approver to see and edit-
suggest before they flip Approval to Approved). That covers the substantive
"internal commentary" use case without needing Gmail-side notes.

Recommend we proceed with Monday-side review only for Milestone 1 and revisit
Gmail-side internal notes once the doc author clarifies the intended feature.

## Caveat

This spike result is based on what I can verify about the Gmail v1 API public
surface. If the client's deployment uses a Workspace add-on or a third-party
draft-collaboration tool (e.g. Front, Hiver, Streak) that integrates with
Gmail, those may expose a "draft notes" feature this spike doesn't cover.
Worth asking explicitly.
