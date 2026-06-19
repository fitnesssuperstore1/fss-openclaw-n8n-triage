---
name: audit_check
description: Final pre-draft gate. Read the outputs of classify_email, select_sop, and draft_response, verify the draft does not violate any no-promise rule, and confirm the routing decision is internally consistent. Force escalation if ANY violation, low confidence, or routing inconsistency is detected. Returns strict JSON only.
---

# Skill: audit_check

## Purpose
Act as the **final independent reviewer** before a draft is allowed to be created. Re-read the three upstream outputs and either pass them through, or force an escalation if something is wrong. This skill is the last line of defense between AI judgment and a customer-visible artifact.

## Inputs
```json
{
  "classification": {
    "primary_lane":   "string",
    "secondary_lane": "string | null",
    "confidence":     "integer 0-100",
    "reasoning":      "string",
    "signals":        ["string"]
  },
  "sop_selection": {
    "sop_id":                        "string | null",
    "sop_status":                    "Active | Reference | Archived | None",
    "use_for_drafting":              "boolean",
    "archived_conflict_noted":       "boolean",
    "archived_conflict_description": "string | null",
    "fallback_action":               "draft | escalate | hold"
  },
  "draft": {
    "draft_subject":     "string",
    "draft_body":        "string",
    "approval_required": "boolean",
    "approver_role":     "CS Lead | Ops Manager | Owner",
    "tone_notes":        "string",
    "uncommitted_items": ["string"]
  }
}
```
(`draft` may be `null` if classification or sop_selection already forced an escalation upstream.)

## Output — RESPOND WITH ONLY THIS JSON (no prose, no markdown fences)

```json
{
  "pass":               <boolean>,
  "violations":         ["<short string per violation found>"],
  "force_escalate":     <boolean>,
  "escalation_reason":  "<one-sentence reason, or null when pass=true>",
  "notify_role":        "CS Lead | Ops Manager | Owner | null"
}
```

Validation that downstream code applies (do not violate):
- `pass` and `force_escalate` MUST be literal booleans.
- `pass == true` ⇔ `force_escalate == false` ⇔ `violations == []` ⇔ `notify_role == null` ⇔ `escalation_reason == null`. These five conditions must agree.
- `notify_role`, when set, MUST be exactly one of `CS Lead`, `Ops Manager`, `Owner`.
- No fields outside the schema. No commentary before or after the JSON.

## Auto-escalate triggers (any of these → `force_escalate = true`)

1. **Finance lane reached this skill at all.** If `classification.primary_lane == "Finance / ACH / Owner Approval"`, force_escalate. notify_role = `Owner`. (Finance never receives an AI-generated customer draft; if we got here something upstream is wrong.)
2. **SOP not usable.** If `sop_selection.use_for_drafting == false`, force_escalate. notify_role = `CS Lead` (low-coverage SOP) or `Ops Manager` (two Active SOPs conflict).
3. **fallback_action says escalate.** If `sop_selection.fallback_action == "escalate"`, force_escalate. notify_role per the rule above.
4. **Low classifier confidence.** If `classification.confidence < 70`, force_escalate. notify_role = `CS Lead`.
5. **Draft violates the no-promise list.** If `draft.draft_body` contains any of:
   - A dollar refund amount or refund commitment
   - A replacement promise
   - A warranty coverage confirmation
   - A SPECIFIC delivery date, time window, or shipping ETA not explicitly authorized by the controlling Active SOP. Procedural language MANDATED by the Active SOP (such as "the Logistics Desk will coordinate delivery" per SOP-02, or "a specialist will follow up" per SOP-04) is NOT a violation. Only invented dates/times/windows count. ORIGINAL HEURISTIC: a delivery date or shipping window beyond what an Active SOP supports
   - A fault, blame, or liability statement
   - A technical outcome promise — meaning a commitment to fix, repair, resolve, deliver, update, or change a specific outcome by a stated point (e.g. "we will update the product page", "this will be resolved by tomorrow", "the bug will be fixed"). Generic acknowledgement that a person or team will look at, investigate, or follow up on the matter is NOT a technical outcome promise and is NOT a violation.
   → record the specific violation in `violations[]` and force_escalate. notify_role = `CS Lead` (or `Owner` if the violation is financial).
6. **Approver mismatch.** If `draft.approver_role` is missing, null, or inconsistent with the lane (e.g. a Finance-lane draft showing CS Lead), force_escalate. notify_role = `Owner`.
7. **Schema inconsistency upstream.** If any required field above is missing, malformed, or contradicts another (e.g. `use_for_drafting=true` but `sop_status` is not `Active`), force_escalate. notify_role = `Ops Manager`.

## Notify-role assignment (when force_escalate is true)

Apply in this priority order:

1. Finance / ACH / payment violation → **Owner**
2. Two Active SOPs in conflict → **Ops Manager**
3. Schema / data-model inconsistency upstream → **Ops Manager**
4. No-promise violation (refund, replacement, warranty, delivery, fault, technical outcome) → **CS Lead**
5. Low confidence or no Active SOP → **CS Lead**
6. Anything else → **CS Lead** (safe default)

## When everything checks out

Set `pass = true`, `force_escalate = false`, `violations = []`, `escalation_reason = null`, `notify_role = null`. The downstream workflow will then create the Gmail draft using the `draft` payload as-is.

## Forbidden
- Never modify the draft body. This skill only judges; it doesn't rewrite.
- Never quote draft content in `escalation_reason` longer than ~80 characters.
- Never return free text outside the JSON.
