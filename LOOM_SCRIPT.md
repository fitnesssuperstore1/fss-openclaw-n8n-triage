# Loom Walkthrough Script (3–5 min)

> Framing line to open with: *"This is a Phase-1 sandbox prototype on an isolated server with synthetic SOPs and synthetic emails — no production access, no real customer data. The goal is to show the routing logic, the safety gates, and how OpenClaw and n8n split the work."*

### 0:00–0:30 — The brief & the auto-fail conditions (set the frame)
- "Five things auto-fail this test. I designed the whole system around preventing them: (1) AI approving ACH, (2) AI auto-sending email, (3) ignoring archived-vs-active SOP conflicts, (4) confusing freight vs parcel, (5) a generic architecture answer."
- "So everything I show maps back to those."

### 0:30–1:15 — The architecture split (the one diagram)
- Show §3 diagram. "n8n does deterministic plumbing — triggers, lookups, creating drafts and Monday cards. OpenClaw does the judgment — classify, read the SOPs, detect conflicts, decide draft-vs-escalate, write the draft."
- Punchline: **"There is no node anywhere in n8n that can send a customer email or move money. So the worst an AI mistake can do is leave a wrong draft sitting unsent. Safety is structural, not just a prompt."**

### 1:15–1:45 — Source of truth (Drive) + the conflict trap
- Show the Drive folders Active / Reference / Archived — these are LIVE-fetched by n8n on every run (Drive Search + Download nodes), so editing an SOP in Drive instantly changes routing.
- Open **SOP-02 (Active)** "Logistics Desk coordinates freight" next to **ARCH-01 (Archived)** "tell the customer to self-schedule." "These conflict on purpose. Active must win, and the conflict must be surfaced — that's Case 10."

### 1:45–3:15 — Live demo (the money shot) — run 3 cases
Run the n8n workflow against the test inbox on three cases (or fall back to `./run-triage.sh` for the fixture-direct path) and show outputs:
1. **Case 1 (happy path):** show the decision JSON → lane = New Orders → and the **draft that appears in the Gmail Drafts folder** (not sent). Point at the `[DRAFT — pending approval]` marker.
2. **Case 6 (ACH):** show `action = escalate`, `approver = Owner`, and that the draft (if any) is a neutral holding note that **commits to no payment**. "This is the auto-fail it would be to confirm that ACH. It escalates instead."
3. **Case 10 (archived conflict):** show `sop_conflict.detected = true`, `controlling_sop = SOP-02 (Active)`, resolution note. "It caught the archived SOP and followed the active one."

### 3:15–3:45 — Routing table + Monday
- Flash the 10-case routing table (§1). "One email, one primary lane. Freight and parcel are deliberately separate lanes."
- Show the Monday board: cards landed in the right lane; ACH/refund cards carry the approval gate.

### 3:45–4:30 — Permissions, eval, and open questions
- §6 permission matrix in one sentence: "AI proposes, a named human disposes; the riskier the action, the higher the approver."
- §7 eval: "Golden set of ~50 emails, and a safety regression suite that re-tests all five auto-fail conditions on every run."
- §9: "Here are the 8 implementation questions I'd want answered before Phase 2 — top one: how do you mark SOP status in Drive today, so retrieval keys off your real signal."

### 4:30–5:00 — Close
- "To recap: Active-only routing with conflict detection, freight ≠ parcel, draft-only, ACH and refunds gated to humans, and a structure where the AI literally cannot send or pay. Happy to walk through the n8n nodes or any SOP in detail."

---
**Pre-record checklist**
- [ ] n8n workflow tested end-to-end on the test inbox (or `./run-triage.sh all` for fixtures); `out/*.decision.json` look correct.
- [ ] Gmail Drafts folder open (show drafts created by the n8n Gmail Create Draft node; verify Sent folder is empty).
- [ ] Monday board open with lane groups.
- [ ] Drive SOP folders open (Active + Archived side by side).
- [ ] DELIVERABLES.md open for the tables.
- [ ] Say "sandbox / synthetic data" at least once.
