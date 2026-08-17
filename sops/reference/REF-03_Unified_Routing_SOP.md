---
sop_id: REF-03
title: Unified Routing SOP (Role Ownership)
status: Reference
control: Controlled
lane: All
applies_to_cases: [internal_01, internal_02, internal_03]
last_reviewed: 2026-08-17
owner: Operations
---

# Unified Routing SOP — Role Ownership (CONTROLLED)

> Controlled routing source. Maps each internal governance / routing domain to
> the ROLE that owns the decision. Roles only — the current person holding a
> role is resolved from the live Org Chart (REF-04) at runtime and is never
> written into code, skills, or fixtures.

## Domain → owning role

| Governance / routing domain | Signals | Owning role |
|---|---|---|
| SOP governance ("which SOP controls / governs X") | "which SOP", "controlling SOP", "SOP governance" | **Ops Manager** |
| Process ownership ("who owns / manages process X") | "who owns", "who manages", "process ownership" | **Ops Manager** |
| Support-channel routing (Gorgias vs internal triage) | "Gorgias", "internal Gmail triage", "support channel" | **CS Lead** |
| Money movement (ACH / wire / payment / bank-detail change) | "ACH", "wire", "routing", "bank change", "invoice payment" | **Owner** |
| Customer operational lanes (orders, freight, install, parcel, sales) | see SOP-00 | per SOP-00 |

## Answerability

- SOP-governance questions have **no single authoritative SOP to cite** in Phase 1,
  so they **escalate** to the owning role (no draft) for an authoritative human answer.
- Process-ownership and support-channel questions **can be answered** from the Org
  Chart / this routing SOP, so they are **drafted pending the owning role's approval**.
