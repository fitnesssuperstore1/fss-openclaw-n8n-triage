---
name: select_sop
description: Pick the controlling SOP for one email's classified workflow lane. Apply the strict Active > Reference > Archived hierarchy. Archived SOPs are NEVER allowed to control routing; if one matches but an Active SOP also controls, set archived_conflict_noted=true and let the Active SOP win — do NOT escalate solely because an archived SOP exists. Returns strict JSON only.
---

# Skill: select_sop

## Purpose
Given a classified email's primary lane and the available SOP catalog, identify the **single controlling SOP** to use for downstream drafting. Apply the Active / Reference / Archived hierarchy correctly. Detect archived-vs-active conflicts for the audit trail without over-escalating.

## Inputs
```json
{
  "primary_lane":   "<one of the 8 lanes>",
  "is_internal":    <boolean — true when the sender is an internal team member>,
  "email_signals":  ["<keyword or phrase>", "..."],
  "available_sops": [
    {
      "id":      "SOP-0X | REF-0X | ARCH-0X",
      "title":   "string",
      "status":  "Active | Reference | Archived",
      "lane":    "<one of the 8 lanes>",
      "content": "full markdown content of the SOP"
    }
  ]
}
```

## Output — RESPOND WITH ONLY THIS JSON (no prose, no markdown fences)

```json
{
  "sop_id":                          "<id of the selected SOP, or null>",
  "sop_status":                      "Active | Reference | Archived | None",
  "use_for_drafting":                <boolean>,
  "archived_conflict_noted":         <boolean>,
  "archived_conflict_description":   "<one-sentence description of the archived SOP that was overridden, or null>",
  "fallback_action":                 "draft | escalate | hold"
}
```

Validation that downstream code applies (do not violate):
- `sop_status` MUST be one of `Active`, `Reference`, `Archived`, `None`.
- `use_for_drafting` MUST be a literal boolean (true/false), never a string.
- `archived_conflict_noted` MUST be a literal boolean.
- `fallback_action` MUST be exactly one of `draft`, `escalate`, `hold`, `route`.
- If `use_for_drafting` is `true`, `sop_status` MUST be `Active`. No exceptions.
- No fields outside the schema. No commentary before or after the JSON.

## Hierarchy rules (CRITICAL — Stage 2 refinement, read carefully)

Apply these in order:

0. **SOP-00 is the Master Triage & Routing Policy** — a meta-policy for the orchestrator, NOT a controlling SOP for any individual email. NEVER set `sop_id` = `SOP-00`. If only SOP-00 looks relevant among the Active SOPs (i.e. no lane-specific Active SOP exists), treat that as "no Active SOP matches" and apply rules 3, 4, or 6 below.

1. **An Active SOP matches the lane** → that Active SOP controls. `sop_id` = its id, `sop_status` = `Active`, `use_for_drafting` = `true`, `fallback_action` = `draft`.

2. **An Active SOP matches AND an Archived SOP also looks relevant with conflicting guidance** → the Active SOP still controls. Set `archived_conflict_noted` = `true` and describe the override in one sentence (e.g. "ARCH-01 prescribes customer self-service; SOP-02 supersedes — Logistics Desk coordinates"). `use_for_drafting` stays `true`. **DO NOT escalate solely because the archived SOP exists.**

3. **No Active SOP matches and only a Reference SOP exists, and `is_internal` is `true`** → this is internal team routing, NOT an escalation. `sop_id` = the Reference id, `sop_status` = `Reference`, `use_for_drafting` = `false`, `fallback_action` = `route`. The Reference SOP names the destination team. No human judgment is needed; the task just goes to that team.

3a. **No Active SOP matches and only a Reference SOP exists, and `is_internal` is `false` (customer-facing email)** → we have context but no controlling SOP for a customer draft. `sop_id` = the Reference id, `sop_status` = `Reference`, `use_for_drafting` = `false`, `fallback_action` = `escalate`.

4. **No Active SOP matches and only an Archived SOP looks relevant** → `sop_id` = the Archived id (for the audit trail), `sop_status` = `Archived`, `use_for_drafting` = `false`, `archived_conflict_noted` = `true`, `fallback_action` = `escalate`.

5. **Two Active SOPs genuinely conflict** (both match the lane with materially different guidance) → `sop_id` = the more-specific Active SOP's id, `sop_status` = `Active`, `use_for_drafting` = `false`, `fallback_action` = `escalate`. This is the only Active-SOP situation that escalates.

6. **No SOP matches at all** → `sop_id` = null, `sop_status` = `None`, `use_for_drafting` = `false`, `fallback_action` = `escalate`.

## Forbidden
- Never set `use_for_drafting` = `true` based on a Reference or Archived SOP.
- Never escalate based on the mere presence of an Archived SOP when an Active SOP clearly controls.
- Never invent an SOP id that isn't in `available_sops`.
- Never select SOP-00 (Master Triage & Routing Policy) as the controlling SOP. It is a meta-policy, not a drafting SOP.
- Never describe SOP content beyond what the input contains.
- Never return free text outside the JSON.
