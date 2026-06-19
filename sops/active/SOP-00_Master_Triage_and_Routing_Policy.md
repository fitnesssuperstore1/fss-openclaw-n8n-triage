---
sop_id: SOP-00
title: Master Triage & Routing Policy
status: Active
lane: All
applies_to_cases: [1,2,3,4,5,6,7,8,9,10]
last_reviewed: 2026-05-01
owner: Operations Manager
---

# Master Triage & Routing Policy

This is the controlling Active SOP. It governs how inbound Gmail is triaged in Phase 1.

## SOP precedence
1. **Active** SOPs control routing decisions.
2. **Reference** SOPs may add context but MUST NOT override an Active SOP.
3. **Archived** SOPs MUST NOT control routing. If an Archived SOP appears relevant, ignore it for the decision and raise a conflict flag noting the Active SOP that supersedes it.

## Workflow lanes
- New Orders / Pending Shipments
- Shipping CS (freight / LTL)
- Parcel / Small Package (UPS, FedEx, USPS)
- Install / Service / Warranty
- Sales CS
- Finance / ACH / Owner Approval
- Product Content / Ecommerce
- Escalate / Needs Human Review

## Core rules
- One email maps to **one primary** workflow. Note secondary lanes, do not split.
- AI may classify, summarize, recommend, and **draft only**. AI MUST NOT auto-send customer email in Phase 1.
- **ACH / payment-sensitive** actions require **owner approval**. AI never confirms, approves, or initiates payment.
- **Freight (LTL) and Parcel are different lanes.** Never merge them.
- Escalate when the source is **conflicting, missing, or unclear**, or confidence is low.

## Required output per email
`{primary_lane, secondary_lanes[], controlling_sop_id, sop_status, conflict_flag, confidence, action: draft|escalate, approval_required, approver_role, reasoning}`
