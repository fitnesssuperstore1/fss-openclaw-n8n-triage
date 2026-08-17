---
sop_id: REF-04
title: Org Chart (MOCK / M1 TEST SOURCE)
status: Reference
control: MOCK — NOT CONTROLLING
mock: true
lane: All
last_reviewed: 2026-08-17
owner: Operations / HR
---

# Org Chart — MOCK / TEST ONLY / NOT CONTROLLING

> **MOCK / TEST ONLY — NOT CONTROLLING.** This is a static sandbox file committed
> for Milestone 1 testing. The addresses below are **mock role mailboxes**, not
> real people and not a live directory. It does **not** represent live Org Chart
> resolution. In production the current role holder is retrieved at runtime from
> the company's controlled Org Chart / HR source. The triage code treats the
> table below as an **M1 test source** only.

## Role -> current holder (M1 TEST MAPPING — mock mailboxes)

The engine parses this table at runtime to resolve an approver ROLE to its
current holder. Exactly one holder per role; a missing or ambiguous (multiple)
match makes the engine fail closed (escalate, `draft=null`).

| Approver role | Mock holder (TEST mailbox) |
|---|---|
| Owner | owner@frenchfitness.com |
| Ops Manager | ops-manager@frenchfitness.com |
| CS Lead | cs-lead@frenchfitness.com |
| Product Lead | product-lead@frenchfitness.com |
