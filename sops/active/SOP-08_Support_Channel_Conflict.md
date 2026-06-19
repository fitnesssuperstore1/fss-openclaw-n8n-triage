---
sop_id: SOP-08
title: Support Channel Conflict (Gorgias vs Gmail)
status: Active
lane: Escalate / Needs Human Review
applies_to_cases: [8]
last_reviewed: 2026-05-08
owner: CS Lead
---

# Support Channel Conflict (Gorgias vs Gmail)

## Trigger
Customer emails (Gmail) saying their support ticket was **closed but the issue is unresolved**, OR the Gmail thread and the Gorgias ticket state disagree (e.g., Gorgias = closed, customer = still broken).

## Routing
Primary lane: **Escalate / Needs Human Review** — the source of truth is **conflicting** across systems. Per Master Policy, conflicting sources escalate.

## Handling
1. Do NOT trust a single channel's status. Surface BOTH the Gorgias ticket state and the Gmail thread to a human.
2. Draft a holding reply: acknowledge, confirm we are re-opening/reviewing, set a callback expectation. No resolution claim.
3. Create an escalation task for the CS Lead with links to both the ticket and the email thread.
4. Once a human reconciles the channels, route to the correct functional lane (shipping, install, etc.).

## Guardrails
- Channel disagreement = escalate, never auto-resolve.

## Draft tone
Apologetic for the gap, reassuring, no resolution promised. Draft-only.
