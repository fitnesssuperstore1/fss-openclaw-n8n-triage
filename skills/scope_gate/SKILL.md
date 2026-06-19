---
name: scope_gate
description: First gate of the triage chain. Decide whether an inbound email is something the Phase 1 sandbox should process (internal team email or leadership email) or whether it is out of scope (customer-facing email owned by Gorgias, or anything unclear). Returns strict JSON only. Customer-facing lanes are NEVER processed by this Phase 1 system.
---

# Skill: scope_gate

## Purpose
Before any classification, SOP lookup, drafting, or audit happens, decide whether the inbound email is in scope for this Phase 1 triage system at all.

This Phase 1 system handles **internal/leadership Gmail triage only**. Customer-facing email is owned by Gorgias and must NEVER be processed here.

If the email is out of scope, the rest of the chain does not run, no Monday item is created, and no Gmail draft is produced.

## Inputs
The user message is a JSON object describing one inbound email:
```json
{
  "from":         "string",
  "to":           "string",
  "subject":      "string",
  "body":         "string",
  "received_at":  "ISO 8601 timestamp"
}
```

If you receive plain text instead of JSON, treat the whole text as the email body and leave the other fields empty (which forces `scope_label: "unknown"` per the rules below — safe default).

## Output — RESPOND WITH ONLY THIS JSON (no prose, no markdown fences)

```json
{
  "in_scope":    <boolean>,
  "scope_label": "internal | leadership | gorgias_owned | unknown",
  "reason":      "<one sentence explaining the decision>",
  "signals":     ["<keyword or phrase 1>", "<keyword or phrase 2>", "..."]
}
```

Validation that downstream code applies (do not violate):
- `in_scope` MUST be a literal boolean (true/false).
- `scope_label` MUST be exactly one of: `internal`, `leadership`, `gorgias_owned`, `unknown`.
- `reason` MUST be a string 10–300 characters explaining which rule triggered the decision.
- `signals` MUST be an array of at most 10 short strings (1–80 chars each) — the literal keywords or address fragments that drove the decision.
- No fields outside the schema. No commentary before or after the JSON.

## Hard rules (apply in this exact order — earlier rules override later ones)

1. **Customer-facing recipient address → out of scope (Gorgias-owned).**
   If the `to` field contains any of the following address fragments (case-insensitive):
   - `sales@`
   - `sales.cs@`
   - `shipping.cs@`
   - `support@`
   - `service@`
   - `cs@`
   - `customer@`
   - `help@`
   - `returns@`
   - any other obviously customer-facing inbox name
   → `in_scope: false`, `scope_label: "gorgias_owned"`. Do not look at anything else.

2. **Internal sender + leadership recipient → in scope (leadership).**
   If the `from` field is from a company-internal domain (or signed as `warehouse`, `ops`, `merch`, `product`, `finance`, `accounts`, `logistics`, etc.) AND the `to` field is a leadership inbox (`leadership@`, `owner@`, `ceo@`, `cto@`, `coo@`, `directors@`, `executive@`, or named leadership-only address)
   → `in_scope: true`, `scope_label: "leadership"`.

3. **Internal sender + internal/operational recipient → in scope (internal).**
   If the `from` field is internal AND the `to` field is an operational/internal inbox (`team@`, `ops@`, `triage@`, `internal@`, `content@`, `merch@`, `warehouse@`, `logistics@`, `accounts@`, `accounts-payable@`, `finance@`, `product@`, named ops team address)
   → `in_scope: true`, `scope_label: "internal"`.

4. **Unclear or missing signals → safe default of out of scope.**
   If you cannot confidently match any of rules 1–3 from the inputs (e.g. `from`/`to` blank, both look ambiguous, customer-vs-internal cannot be determined from the body, signatures missing, etc.)
   → `in_scope: false`, `scope_label: "unknown"`. The safe default is to NOT process. A human can re-route by hand if needed.

## How to detect "internal sender"

A sender is internal when ANY of these are true:
- The `from` email domain matches a known company domain (e.g. `@frenchfitness.com`, `@fitnesssuperstore.com`, or the configured internal domain at deployment time).
- The signature in the body identifies them as `warehouse`, `ops`, `merch`, `product`, `finance`, `accounts`, `logistics`, or another internal role.
- The subject contains `[internal]`, `[team]`, or `[ops]` as a tag.
- The body addresses "team" or "the team" without any customer-context (no order number, no product complaint, no shipping question).

If none of these apply, treat the sender as external (which usually then triggers rule 1 or rule 4).

## Reasoning style

- `reason` must name the specific rule and signal that drove the decision, e.g. "Recipient `support@frenchfitness.com` matches customer-facing inbox list (rule 1) → gorgias_owned" or "Sender signed `warehouse` and recipient is `team@` operational inbox (rule 3) → internal".
- `signals` is the array of literal address fragments, signature words, or subject tags extracted from the email that justified the call (e.g. `["support@frenchfitness.com", "[internal]", "Tom (warehouse)"]`).

## Forbidden

- Never invent a `scope_label` outside the four allowed values.
- Never set `in_scope: true` if rule 1 matches (customer-facing recipient always wins).
- Never default to `in_scope: true` when unclear. The safe default is FALSE.
- Never classify the email's workflow lane — that is the next skill's job (`classify_email`).
- Never read or quote the SOP catalog — this skill works only from the email itself.
- Never return any text outside the JSON.
