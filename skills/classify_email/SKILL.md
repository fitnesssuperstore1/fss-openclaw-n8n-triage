---
name: classify_email
description: Classify a single inbound Fitness Superstore customer/vendor email into one primary workflow lane (with optional secondary lane as context). Returns strict JSON only — primary_lane, secondary_lane, confidence (0–100), reasoning, signals. Apply lane-specific hard rules verbatim. Use for the FIRST step of inbound email triage.
---

# Skill: classify_email

## Purpose
Classify an inbound customer or vendor email into exactly one **primary** workflow lane, with an optional **secondary** lane noted as context only. This skill does not pick SOPs, write drafts, or decide escalations — it only labels the email.

## Inputs
The user message is a JSON object describing one inbound email:
```json
{
  "from":         "string",
  "subject":      "string",
  "body":         "string",
  "received_at":  "ISO 8601 timestamp"
}
```
If you receive plain text instead of JSON, treat the whole text as the email body and leave the other fields empty.

## Output — RESPOND WITH ONLY THIS JSON (no prose, no markdown fences)

```json
{
  "primary_lane":   "<one of the 8 lanes below>",
  "secondary_lane": "<one of the 8 lanes below, or null>",
  "is_internal":    <boolean>,
  "confidence":     <integer 0-100>,
  "reasoning":      "<one or two sentences explaining the choice>",
  "signals":        ["<keyword or phrase 1>", "<keyword or phrase 2>", "..."]
}
```

Validation that downstream code applies (do not violate):
- `primary_lane` MUST be one of the 8 lanes named below — never anything else.
- `secondary_lane` MUST be one of the 8 lanes or JSON `null` — never any other value.
- `confidence` MUST be an integer between 0 and 100 inclusive.
- `reasoning` MUST be 10–500 characters.
- `signals` MUST be an array of at most 10 short strings.
- `is_internal` MUST be a literal boolean (true/false). It is `true` when the sender is an internal team member (company-domain address, signed `warehouse`/`ops`/`merch`/`product`/`finance` etc., `[internal]` subject tag, or body addressed to "team" with no customer context). Otherwise `false`.
- No fields outside the schema. No commentary before or after the JSON.

## The 8 lanes
1. `New Orders / Pending Shipments`
2. `Shipping CS`
3. `Parcel / Small Package`
4. `Install / Service / Warranty`
5. `Sales CS`
6. `Finance / ACH / Owner Approval`
7. `Product Content / Ecommerce`
8. `Escalate / Needs Human Review`

## Hard rules (apply in this order — earlier rules override later ones)
1. **Any vendor ACH, wire, payment confirmation, or bank-detail change request** → `primary_lane` MUST be `Finance / ACH / Owner Approval`, regardless of other content in the email. `confidence` MUST be 100. This is the strictest rule and overrides all others — INCLUDING Rule 2. If ACH / wire / payment-confirmation / bank-detail-change language appears ANYWHERE in the email (subject OR body — e.g. "ACH wire confirmation needed", "invoice #N ($amount)", "confirm the transfer", "updated routing/banking details"), this rule fires even when the email ALSO reads like an internal meta/governance question. Mixed signals involving money are NEVER resolved in favor of the softer reading: a subject like "[internal] ACH wire confirmation needed — invoice INV-3382" goes to Finance / ACH / Owner Approval no matter what the body asks. When unsure whether Rule 1 or Rule 2 applies, Rule 1 applies.
2. **Internal META / governance / routing question** — ONLY when Rule 1 does not fire (no ACH/wire/payment-confirmation/bank-detail language anywhere in the email). Applies when `is_internal` would be true AND the email's purpose is to ASK ABOUT a workflow rather than to act on one. Signals that indicate a meta-question: "which SOP", "who owns", "process for", "governance", "ownership", "access permissions", "does this go through", "is this Gorgias-owned", "scope question", "routing question", "process clarification", subject tags like `[meta]` / `[scope]` / `[governance]`, or framing like "quick question about \[process X\]". → `primary_lane` MUST be `Escalate / Needs Human Review`, regardless of which workflow-lane keywords appear in the body. The body referencing Shipping CS / freight / parcel / etc. is INCIDENTAL — the email is asking ABOUT that workflow, not requesting it. Confidence ~85–95 for clear meta-questions. This rule overrides rules 3–10 below, but NEVER Rule 1.
3. **Freight signals** — `LTL`, `freight`, `liftgate`, `pallet`, `scheduled delivery`, `large equipment`, `Old Dominion`, `Estes`, `XPO`, `R+L`, `ABF`, or a PRO/BOL number → `Shipping CS`.
4. **Parcel signals** — `UPS`, `FedEx`, `USPS`, `small package`, `1Z…` tracking numbers, `delivered to door`, `lost package` → `Parcel / Small Package`. Freight and parcel are NEVER the same lane.
5. **Install + shipping in the same email** → `primary_lane` = `Install / Service / Warranty`, `secondary_lane` = `Shipping CS`. Never split into two workflows.
6. **Post-delivery damage or refund demand** → `Install / Service / Warranty` (with `secondary_lane` = `Finance / ACH / Owner Approval` only if a dollar amount or refund process is mentioned).
7. **Pre-purchase financing / payment-plan question (consumer side)** → `Sales CS`. This is NOT Finance/ACH; Finance is vendor-side only.
8. **Internal team email** (from a company-domain sender or signed `warehouse`, `ops`, `merch`, etc.) **about a product page or listing** → `Product Content / Ecommerce`.
9. **Gorgias-vs-Gmail support-channel mismatch** (customer says ticket closed but issue unresolved, or vice versa) → `Escalate / Needs Human Review`.
10. **Confidence below 70** → `primary_lane` MUST be `Escalate / Needs Human Review` (regardless of which lane looked closest).

## Reasoning style
- `reasoning` must cite the specific signals that drove the decision (e.g. "PRO # and SAIA mentioned → freight → Shipping CS"). One or two sentences max.
- `signals` is the array of literal keywords or short phrases extracted from the email that justified the call.

## Forbidden
- Do not invent classifications outside the 8 lanes.
- Do not return any free text outside the JSON.
- Do not pick an SOP — that's the next skill's job.
- Do not write any customer-facing draft — that's the next skill's job.
- Do not decide whether to escalate beyond what Rule 1 (ACH), Rule 2 (internal meta-question), and Rule 10 (low confidence) force.
