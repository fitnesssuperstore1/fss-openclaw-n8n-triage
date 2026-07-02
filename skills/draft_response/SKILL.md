---
name: draft_response
description: Write a customer-safe draft reply grounded strictly in the supplied Active SOP. Phase 1 — every draft is for human approval, never sent. Hard no-promise list — never commit refund amounts, replacements, warranty coverage, delivery dates, fault/blame, or technical outcomes. Anything the customer asked for that the draft refuses to commit must go into uncommitted_items[]. Returns strict JSON only. Must NOT be invoked for the Finance / ACH / Owner Approval lane.
---

# Skill: draft_response

## Purpose
Generate a single customer-safe draft reply for the email at hand, grounded **strictly** in the supplied Active SOP and the lane's tone. Every draft requires a human approver before send. The draft never auto-sends.

## When this skill MUST NOT be invoked
- When `primary_lane` is `Finance / ACH / Owner Approval`. Finance escalations never receive a customer-facing draft from this skill.
- When `select_sop.use_for_drafting` is `false`. Without an Active controlling SOP, this skill produces nothing.

## Inputs
```json
{
  "email": {
    "from":    "string",
    "subject": "string",
    "body":    "string"
  },
  "sop_content":              "the full markdown content of the controlling Active SOP",
  "lane":                     "<one of the 8 lanes>",
  "archived_conflict_noted":  <boolean — context only, do NOT mention to the customer>
}
```

## Output — RESPOND WITH ONLY THIS JSON (no prose, no markdown fences)

```json
{
  "draft_subject":      "Re: <original subject, or a clear new subject>",
  "draft_body":         "<the reply body — see no-promise rules below>",
  "approval_required":  true,
  "approver_role":      "CS Lead | Ops Manager | Owner",
  "tone_notes":         "<one sentence describing tone choices, e.g. 'customer is upset, lead with empathy'>",
  "uncommitted_items":  ["<a short string per request the draft refused to commit>"]
}
```

Validation that downstream code applies (do not violate):
- `approval_required` MUST be the literal boolean `true`.
- `approver_role` MUST be exactly one of `CS Lead`, `Ops Manager`, `Owner`.
- `uncommitted_items` MUST be an array (may be empty).
- `draft_body` MUST be a clean, customer-facing reply ONLY. It MUST NOT contain
  any internal metadata: no `[DRAFT — pending human approval | lane: … | SOP: … ]`
  footer, no lane names, no SOP/REF/ARCH ids, no internal policy names, and no
  "pending approval" markers. All of that internal metadata lives ONLY in the
  Monday card / audit fields — never in the body the customer would see. (The
  approval-pending state is tracked by the workflow + the Monday "Awaiting
  Review" status, not by text inside the draft.)
- No fields outside the schema. No commentary before or after the JSON.

## Hard rules — the no-promise list

The `draft_body` MUST NOT contain ANY of the following, EVER, regardless of what the customer asks for:

- A specific **refund amount** (dollar figure) or a commitment to issue a refund
- A **replacement promise** ("we'll send you a new unit", "we'll ship a replacement")
- A **warranty coverage confirmation** ("this is covered under warranty", "yes, warranty applies")
- A **SPECIFIC delivery date, time window, or shipping ETA** not explicitly authorized by the controlling Active SOP. Procedural language MANDATED by the Active SOP (e.g. "the Logistics Desk will coordinate delivery" per SOP-02, or "a specialist will follow up" per SOP-04) is NOT a violation — only invented dates/times/windows count
- A **fault, blame, or liability statement** ("the carrier damaged this", "our fault", "we're liable")
- A **technical outcome promise** ("this will fix the issue", "this resolves it")
- Any **financial, contractual, or legal commitment** of any kind

If the customer asks for any of the above, the draft must:

1. **Acknowledge** the request (mention what they asked for).
2. **Express empathy** if the situation is emotional (damage, frustration, delay).
3. **State** that a team member will review and follow up — never that the issue is resolved.
4. **Add the dodged commitment** to `uncommitted_items` so the human approver knows exactly what still needs an answer.

## Tone matrix (apply to draft_body, not to the JSON itself)

- **Damage / refund (SOP-04):** lead with apology and empathy; never commit a refund amount; ask for photos if SOP-04 prescribes it; close with "a specialist will follow up within one business day" only if the SOP supports that.
- **Pre-sale / financing (SOP-05):** helpful and direct; **never quote interest rates or APRs**; redirect to the financing partner page or a sales rep.
- **Tracking / shipping (SOP-01, SOP-02):** factual and specific to the order; never guarantee a delivery date beyond the SOP's ranges; if no firm date is in the SOP, state the typical range and that tracking will follow.
- **Install / warranty (SOP-03):** practical and procedural; outline the next steps a human will take; never confirm warranty coverage outright.
- **Parcel claim (SOP-07):** factual; outline the parcel-claim process; never promise carrier outcomes.
- **Channel-conflict (SOP-08):** acknowledge confusion; do not pick sides on what the prior ticket said; route to a human.

## Approver assignment

Pick `approver_role` based on the lane and the email content:

- Damage, refund demand, warranty claim → **CS Lead**
- Two genuinely-conflicting Active SOPs (rare) → **Ops Manager**
- Anything that crossed into payment/financial territory and slipped through to this skill anyway → **Owner** (and add a violation note in `tone_notes`)
- Default for normal customer drafts → **CS Lead**

## Forbidden

- Never auto-send. There is no "send" path; you only produce a draft.
- Never mention to the customer that an archived SOP existed.
- Never quote SOP IDs or internal policy names in the customer-facing body.
- Never invent facts not present in the email or the supplied SOP content.
- Never return free text outside the JSON.
