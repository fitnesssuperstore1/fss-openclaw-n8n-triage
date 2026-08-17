---
sop_id: REF-03
title: Unified Routing SOP (MOCK / M1 TEST SOURCE)
status: Reference
control: MOCK — NOT CONTROLLING
mock: true
lane: All
applies_to_cases: [internal_01, internal_02, internal_03]
last_reviewed: 2026-08-17
owner: Operations
---

# Unified Routing SOP — MOCK / TEST ONLY / NOT CONTROLLING

> **MOCK / TEST ONLY — NOT CONTROLLING.** This is a static sandbox file committed
> for Milestone 1 testing. It is **not** a live routing source and does **not**
> represent live Org Chart / routing resolution. In production this mapping comes
> from the company's controlled Unified Routing SOP, retrieved at runtime. The
> triage code treats the block below as an **M1 test configuration** only.

## Domain -> owning role (M1 TEST MAPPING — not live-source resolution)

The triage engine parses this list at runtime to decide which ROLE owns an
internal governance/routing question. Roles only — the person holding a role is
looked up separately in the mock Org Chart (REF-04).

- sop_governance: Owner
- process_ownership: Ops Manager
- support_channel: CS Lead
- money_movement: Owner

> Note: `sop_governance` routes to **Owner** in this M1 test config because SOP
> document control is temporarily unassigned; Owner is the authoritative
> escalation. The current person is deliberately kept out of code and fixtures.

## Answerability (M1 test behavior)

- `sop_governance` — no single authoritative SOP to cite, so **escalate** to the
  owning role (no draft).
- `process_ownership`, `support_channel` — a controlling Active source (SOP-08)
  supports an answer, so **draft pending** the owning role's approval, but only
  after the draft passes the normal strict schema + audit/no-promise gate.
- If any required mock source (this file, REF-04, or the controlling SOP) is
  missing, non-Active, ambiguous, or conflicting, the engine **fails closed**:
  escalate with `draft=null`.
