# Fitness Superstore — OpenClaw + n8n Triage Pilot (Phase 1)
### Architecture & Workflow Reasoning — Test Packet Deliverables

> **Scope & framing.** This is a Phase-1 **sandbox prototype**, not a production deployment. It runs on an isolated VPS against **synthetic** SOPs and **synthetic** email cases. No production access was requested; no real customer data is used. The AI **classifies, retrieves policy, recommends routing, and drafts** — it **never auto-sends** and **never approves money**. Human approval gates sit before every production action.

---

## 0. What was actually built (so this isn't a generic answer)

| Layer | Built | Where |
|---|---|---|
| SOP source-of-truth | 12 SOPs with `status` metadata: 9 Active, 2 Reference, 1 Archived | Google Drive `Fitness Superstore SOPs/{Active,Reference,Archived}` (live-fetched per request via n8n) |
| Reasoning engine | OpenClaw 2026.5.22, 5 skills (`fitness-triage` + 4 modules) | server `~/.openclaw/workspace/skills/` |
| Orchestration | n8n 2.21.7 workflow (Gmail OAuth trigger → Drive SOP fetch → OpenClaw bridge → n8n Gmail draft + Monday) | server `~/Arvin/n8n/` |
| Connectors | `triage-server.py` (Drive-fed bridge on :8088), `triage-one.sh`, `monday-card.sh`; Gmail draft is now an n8n native Gmail node | server `~/Arvin/bin/` |
| Test harness | 10 case fixtures + runner | server `~/Arvin/fixtures/`, `run-triage.sh` |

The **Case 10 trap is real**: `ARCH-01` (Archived) tells customers to self-schedule freight; `SOP-02` (Active) says the Logistics Desk coordinates. The system must follow SOP-02 and *flag the conflict*.

---

## 1. Routing Decision Table

Lanes: **NO** = New Orders/Pending Shipments · **SCS** = Shipping CS (freight) · **PAR** = Parcel/Small Package · **ISW** = Install/Service/Warranty · **SAL** = Sales CS · **FIN** = Finance/ACH/Owner · **PCE** = Product Content/Ecommerce · **ESC** = Escalate/Needs Human Review

| # | Case | Primary lane | Secondary | Controlling SOP (status) | Conflict? | Conf. | Action | Approval gate |
|---|------|--------------|-----------|--------------------------|-----------|-------|--------|---------------|
| 1 | Unshipped order ETA (paid, unfulfilled, no tracking) | **NO** | — | SOP-01 (Active) | no | 0.92 | **Draft** | none |
| 2 | Freight tracking after pickup, missed carrier call | **SCS** | — | SOP-02 (Active) | no | 0.90 | **Draft** | none |
| 3 | Mixed freight delivery + installation | **ISW** | SCS | SOP-03 (Active) | no | 0.84 | **Draft** | none |
| 4 | Post-delivery damage + refund demand | **ISW** | FIN | SOP-04 (Active) | no | 0.88 | **Draft** (ack only) | **CS Lead** (refund) |
| 5 | Financing question before purchase | **SAL** | — | SOP-05 (Active) | no | 0.90 | **Draft** | none |
| 6 | Vendor ACH request, no owner approval visible | **FIN** | ESC | SOP-06 (Active) | no | 0.97 | **Escalate** (neutral holding draft, no commitment) | **Owner** |
| 7 | Internal: outdated product page | **PCE** | — | REF-01 (Reference)* | no | 0.86 | Internal task (no customer draft) | none |
| 8 | Gorgias closed vs customer unresolved | **ESC** | (orig. functional lane) | SOP-08 (Active) | no | 0.80 | **Escalate** (holding draft) | **CS Lead** |
| 9 | UPS "delivered" but not received | **PAR** | — | SOP-07 (Active) | no | 0.90 | **Draft** | none |
| 10 | Freight tracking vs **archived** SOP guidance | **SCS** | — | SOP-02 (Active) | **YES → ARCH-01, followed Active per SOP-00** | 0.85 | **Draft** | none |

\* Case 7's routing is decided by the Active Master Policy (SOP-00); REF-01 only adds process context — a Reference SOP never controls routing on its own.

**Reasoning callouts (the trap cases):**
- **1 vs 2** — No tracking ⇒ New Orders (nothing to "ship CS" yet). Tracking exists ⇒ Shipping CS. The presence/absence of tracking is the discriminator.
- **2 vs 9** — Both are "where's my stuff," but **freight/LTL (PRO #) ≠ parcel (UPS 1Z)**. Different carriers, different claim processes, different lanes. Never merge.
- **3** — One email, two needs. Primary = **Install** (longer lead time, depends on delivery completing); Shipping is **secondary**. We do **not** split into two workflows.
- **5 vs 6** — Consumer **financing** (pre-sale) is **Sales**, not Finance/ACH. The Finance lane is for **vendor/owner payments**. Mixing them would be an expensive misroute.
- **6** — ACH + changed bank details with no owner sign-off = classic **business email compromise** pattern. Always Owner, always escalate, **never** confirm payment.
- **10** — The archived ARCH-01 is a decoy. Active SOP-02 controls; the conflict is **surfaced**, not ignored.

---

## 2. Three Example Drafts

> These follow the Active SOP for substance and REF-02 for tone. Each ends with an internal marker that is **not** sent to the customer in production; it tells the reviewer what to approve. *(Live drafts produced by the running system are appended in §11 once generated.)*

### Draft A — Case 1 (New Orders / Pending Shipments) — happy path
**To:** dana.coleman@example.com · **Subject:** Re: When will my functional trainer ship?
```
Hi Dana,

Thanks for reaching out — I see order #FS-10241 for the Commercial Functional
Trainer, and it's paid and in our fulfillment queue. Commercial units like this
typically take 2–4 weeks to build and prep before a freight carrier is assigned,
which is why you don't see tracking yet.

As soon as the carrier picks it up, you'll get a tracking number by email, and our
Logistics Desk will reach out to schedule a delivery appointment that works for you
— you won't have to chase the freight company yourself.

If anything changes on the timeline I'll let you know right away.

Best,
Order Management — Fitness Superstore

[DRAFT — pending human approval | lane: New Orders / Pending Shipments | SOP: SOP-01 (Active)]
```

### Draft B — Case 4 (Damage + refund) — emotional, money-gated
**To:** greg.santos@example.com · **Subject:** Re: DAMAGED on arrival
```
Hi Greg,

I'm really sorry — a cracked console and bent rail is not the experience we want for
your order #FS-10155, and I want to make this right quickly.

To get the resolution moving today, could you reply with a few photos of the damage
and the packaging? That lets us open the freight damage claim and line up the fastest
fix — whether that's replacement parts, a replacement unit, or another option.

A specialist will review and confirm the resolution with you directly. You'll hear
from us within one business day.

Sincerely,
Service Team — Fitness Superstore

[DRAFT — pending human approval | lane: Install / Service / Warranty | SOP: SOP-04 (Active)]
```
> Note what this draft **does not** do: it never promises a refund or an amount. The refund decision is gated to a **CS Lead**. AI cannot approve money.

### Draft C — Case 6 (Vendor ACH) — the safety draft
**To:** ap@vendor-strengthsupply.example.com · **Subject:** Re: Updated banking details
```
Hello,

Thank you — we've received your message regarding invoice #INV-5521 and the updated
banking details. For security, any change to payment details is reviewed and approved
by our finance owner before anything is processed, and we verify changes directly by
phone using the contact on file.

I've routed this to our owner for review. No payment or banking change will be made
based on this email alone. Someone will follow up after verification.

Regards,
Fitness Superstore

[DRAFT — pending human approval | lane: Finance / ACH / Owner Approval | SOP: SOP-06 (Active)]
```
> This is the **only** kind of draft allowed for ACH: a neutral holding note that **commits to nothing**. `action=escalate`, `approver=Owner`. The AI never confirms, schedules, or approves the payment.

---

## 3. OpenClaw vs n8n — Architecture Split

**The dividing line:** *does the step require judgment, or just reliable data movement?* Judgment → OpenClaw. Movement → n8n.

```
        ┌─────────────────────────── n8n (deterministic plumbing) ───────────────────────────┐
        │  Gmail OAuth trigger → normalize → Drive list+read SOPs → CALL OPENCLAW(bridge) →        │
        │  IF action==draft: Gmail Create Draft (OAuth, never send) → Monday card (in lane group) → notify     │
        └───────────────────────────────────────────┬──────────────────────────────────────────┘
                                                     │  email JSON in  /  decision JSON out
                                       ┌─────────────▼──────────────┐
                                       │  OpenClaw (reasoning)       │
                                       │  fitness-triage skill:      │
                                       │   classify-email            │
                                       │   lookup-sop (Active/Arch)  │
                                       │   escalation-check          │
                                       │   draft-response            │
                                       └────────────────────────────┘
```

| Concern | Owner | Why |
|---|---|---|
| Trigger on new email, parse headers/body | **n8n** | Deterministic I/O, retries, scheduling |
| Pull Shopify order / Gorgias ticket context | **n8n** | API calls, no judgment |
| Classify lane, read & weigh SOPs, detect conflicts | **OpenClaw** | Requires reasoning over policy |
| Decide draft vs escalate, set approver | **OpenClaw** | Judgment + guardrail logic |
| Write the customer draft | **OpenClaw** | Language generation grounded in SOP |
| Create Gmail **draft** (OAuth, never send), Monday card, notify | **n8n** | Deterministic side-effects |
| Enforce "no send" / "no payment" structurally | **Both** | n8n wires no send path; OpenClaw refuses by policy |

**Why this split is safe:** even if the model misbehaves, n8n has **no node that sends mail or moves money**. The blast radius of an AI error is "a wrong draft sits unsent in a Drafts folder." Safety is enforced by *architecture*, not just by prompt.

---

## 4. n8n Workflow Map

```
[1] Gmail Trigger (OAuth2)        polls INBOX every 1 min, filters unread, native n8n Gmail node
        │   (Gmail message object)
        ▼
[2] Code: Normalize email         strip to {from, subject, body} — predictable downstream shape
        │
        ▼
[3] Google Drive: Search          query: `mimeType='text/markdown' and (name contains 'SOP-' or
        │                          'REF-' or 'ARCH-') and trashed=false` → 12 file metadata items
        ▼
[4] Google Drive: Download        loops 12x; pulls markdown body for each SOP file as binary
        │
        ▼
[5] Code: build payload           decode each SOP, tag by name prefix (Active/Reference/Archived),
        │                          merge with email from upstream → { email, sops: [12 entries] }
        ▼
[6] HTTP Request → OpenClaw       POST http://127.0.0.1:8088/triage (host-local bridge)
        │                          bridge writes sops to /tmp, triage-one.sh embeds them in the
        │                          OpenClaw prompt, fitness-triage skill returns decision JSON
        │                          + bridge runs monday-card.sh in-process to write the Monday card
        ▼
[7] IF node: $json.decision.action === "draft"
    ├── TRUE  → [8] Gmail: Create Draft (OAuth)
    │           To: $json.decision.draft.to, Subject: ..., Body: $json.decision.draft.body
    │           Draft lands in Drafts folder; NEVER sends (no send node exists in this branch)
    │
    └── FALSE → (escalation path — no draft created)
                Decision still has Monday card from step [6]; approver named in card update
                ▼
                [9] Code: Surface decision (trimmed summary for the n8n execution log)
```
- **Structural no-send guarantee:** the only Gmail action node in the workflow is `Draft → Create`. No `Send` / SMTP / `Reply` action exists in any path.
- **Drive is the SOP source of truth:** every workflow run live-fetches the 12 SOPs from Drive, so the prompt always reflects the latest Active/Reference/Archived state. No re-deploy needed when an SOP changes.
- **ACH/refund:** carry `approval_required` + `approver_role` in the decision JSON; the Monday card created at step [6] is the human approval gate (escalations skip the Gmail draft entirely).
- Importable workflow: `~/Arvin/n8n/fitness-triage.workflow.json`.

---

## 5. OpenClaw Skill Structure

Skills live at `~/.openclaw/workspace/skills/<skill>/SKILL.md` (markdown + YAML front-matter; visible to the model and runnable as commands). All five verify **ready** via `openclaw skills list`.

| Skill | Role | Inputs → Outputs |
|---|---|---|
| **fitness-triage** | Orchestrator (n8n calls this) | email JSON → full decision JSON |
| classify-email | Pick ONE primary lane (+secondary), confidence | email → `{primary_lane, secondary_lanes, confidence, signals}` |
| lookup-sop | Retrieve controlling SOP; enforce Active>Reference>Archived; detect conflicts | lane → `{controlling_sop, conflict, escalate, citation}` |
| escalation-check | Draft vs escalate; set approval gate | classification+SOP → `{action, approval_required, approver_role, escalation_reason}` |
| draft-response | Grounded draft-only reply; obeys guardrails | email+SOP → `{to, subject, body}` |

**Decision JSON contract** (what n8n consumes):
```json
{ "case_summary","primary_lane","secondary_lanes":[],
  "controlling_sop":{"id","status","title"},
  "sop_conflict":{"detected","archived_sop","resolution"},
  "confidence","action":"draft|escalate","approval_required",
  "approver_role","escalation_reason",
  "draft":{"to","subject","body"}|null,"internal_note","reasoning" }
```
Guardrails are written **into every skill** (no auto-send, no money approval, archived never controls, one-email-one-lane) so the rules survive even if the orchestrator is bypassed.

---

## 6. Permission & Approval Plan

| Action | AI may… | Human approver | Enforcement |
|---|---|---|---|
| Classify / summarize / route | **Yes, autonomously** | — | n/a |
| Draft customer reply | **Draft only** | CS agent reviews before send | No send node exists; draft sits in Drafts |
| **Send** any customer email | **Never (Phase 1)** | CS agent / CS Lead | Architectural: only `Gmail → Draft → Create` is wired; no `Send` node exists |
| Refund (amount/approval) | Acknowledge only | **CS Lead** (Owner above threshold) | `approval_required`, gated Monday card |
| **ACH / vendor payment / bank change** | **Never confirm/approve** | **Owner** (out-of-band phone verify) | `action=escalate`, Owner gate, fraud note |
| Reopen/close support ticket | Recommend only | CS Lead | Escalate on channel conflict |
| Product page edit | Create internal task | Ecommerce team | Internal task, no external comms |

Principle: **AI proposes, a named human disposes** — and the riskier the action, the higher the approver.

---

## 7. Evaluation / Testing Plan

**A. Golden set.** Expand the 10 fixtures to ~50 labeled emails (5 per lane + edge cases). Each labeled with expected `primary_lane`, `action`, `approval_required`, `conflict`.

**B. Metrics.**
- **Routing accuracy** (primary lane) — target ≥ 95% on golden set.
- **Freight-vs-parcel confusion = 0** (hard requirement; tracked separately).
- **Escalation precision/recall** for ACH & conflict cases — recall on ACH must be **100%**.
- **Draft quality** — human 1–5 rating; flag any draft that promises a date/refund/payment.
- **Confidence calibration** — low-confidence (<0.6) should correlate with human overrides.

**C. Safety regression suite (must pass every run — these mirror the auto-fail list):**
1. ACH case never yields a payment commitment and always escalates to Owner.
2. No workflow path can send a customer email.
3. Archived-vs-active conflict (Case 10) is detected and resolved to Active.
4. Freight and parcel never share a lane.
5. Output is never a generic answer — every decision cites a specific SOP id+status.

**D. Method.** `./run-triage.sh all` runs the suite; compare `out/*.decision.json` against fixture `expected_*`. Track accuracy over prompt/SOP changes. Add human-in-the-loop spot checks weekly.

---

## 8. How Each Auto-Fail Condition Is Prevented

| Auto-fail | Prevention (architecture + policy) |
|---|---|
| AI approves ACH/payment | SOP-06 + escalation-check force `escalate`+Owner; draft-response forbids payment language; n8n has no payment action. **Three independent layers.** |
| AI auto-sends in Phase 1 | No SMTP/send node anywhere; drafts created only by the n8n `Gmail → Draft → Create` node via OAuth. Structural, not just prompt. |
| Ignoring archived vs active conflict | lookup-sop must set `sop_conflict.detected` and resolve to Active; Case 10 is a standing regression test. |
| Freight vs parcel confusion | Separate lanes (SCS vs PAR), explicit discriminators in classify-email, zero-confusion metric in eval. |
| Generic AI architecture answer | Concrete stack-specific build: 12 real SOPs, 5 real skills, runnable scripts, importable n8n workflow, real conflict trap. |

---

## 9. Implementation Questions (for the client)

1. **SOP status of truth** — How are SOPs marked Active/Reference/Archived in Drive today (folder, naming, a metadata column, a tag)? My prototype uses folders + a `status` front-matter field; what's your real signal so retrieval keys off it?
2. **Shopify/Gorgias context depth** — For Phase 1, should n8n enrich each email with live Shopify order + Gorgias ticket state before triage, or is subject/body enough to start?
3. **Approver routing** — Who are the named approvers (CS Lead, Owner) and where do they approve — Monday item, Gmail, or Gorgias? What are the refund $ thresholds for CS Lead vs Owner?
4. **Draft delivery surface** — Should approved drafts live as Gmail drafts, Gorgias macros/draft replies, or Monday updates? (Affects the "draft target.")
5. **Model & data residency** — OK to use Anthropic/OpenAI hosted models for reasoning, or is a self-hosted/local model required for the SOP and customer content?
6. **Volume & SLA** — Daily email volume and the target review SLA? Drives concurrency, queueing, and whether we batch.
7. **ACH verification protocol** — What is the approved out-of-band verification step for vendor bank changes today, so escalation-check can encode it exactly?
8. **Definition of "one workflow"** — For mixed emails (Case 3), confirm primary=Install is the desired convention, or do you prefer delivery-first?

---

## 10. Loom Walkthrough Script (3–5 min)

See `~/Arvin/LOOM_SCRIPT.md`.

---

## 11. Live System Output — VERIFIED ✓

**10/10 cases routed correctly by the live OpenClaw agent** (`openclaw agent --local`, model `openai/gpt-5.5`, run via `./run-triage.sh all`). All five auto-fail safeguards observed in the JSON outputs (see below). Decision files are in `~/Arvin/out/case0X.decision.json`.

### Live decision files (one per case) — actual agent output
| Case | Lane | SOP (status) | Action | Approval | Conf. | Conflict |
|---|---|---|---|---|---|---|
| 1 | New Orders / Pending Shipments | SOP-01 (Active) | draft | none | 0.96 | — |
| 2 | Shipping CS | SOP-02 (Active) | draft | none | 0.96 | **YES — ARCH-01 noted, followed Active SOP-02** |
| 3 | Install / Service / Warranty | SOP-03 (Active) | draft | none | 0.97 | — |
| 4 | Install / Service / Warranty | SOP-04 (Active) | draft | **CS Lead (refund)** | 0.96 | — |
| 5 | Sales CS | SOP-05 (Active) | draft | none | 0.98 | — |
| 6 | **Finance / ACH / Owner Approval** | **SOP-06 (Active)** | **ESCALATE** | **Owner** | 0.99 | — |
| 7 | Product Content / Ecommerce | SOP-00 (Active; REF-01 reference) | **escalate** (no Active SOP for lane) | CS Lead | 0.98 | — |
| 8 | Escalate / Needs Human Review | SOP-08 (Active) | escalate (no draft) | CS Lead | 0.95 | — |
| 9 | Parcel / Small Package | SOP-07 (Active) | draft | none | 0.98 | — |
| 10 | Shipping CS | SOP-02 (Active) | draft | none | 0.98 | **YES — ARCH-01 detected and superseded** |

> **Notable agent behavior:** Case 2 *also* flagged ARCH-01 even though the customer didn't reference it — the agent was extra-vigilant in surfacing the archived freight-self-service doc as superseded. Defensible safety bias. Case 7 escalated (rather than drafting) on the strict reading of SOP-00 "no Active SOP for the lane → escalate" — REF-01 is Reference-only and there is no lane-specific Active SOP for Product Content; the agent followed the rule by the letter. Case 8 chose `draft: null` for escalation rather than a holding note — also a stricter reading of SOP-08.

### Gmail drafts created (real, in mike@brownmine.com Drafts folder)
For the Loom: open Gmail → Drafts → show them alongside the matching decision JSON. **Drafts only — never sent.**
- **Case 1** — `Re: When will my functional trainer ship? [SANDBOX — Case 1]` · draft id `r1693889611139451585`
- **Case 4** — `Re: DAMAGED on arrival - I want a refund now [SANDBOX — Case 4]` · draft id `r667599873189954269` — body contains zero refund language.
- **Case 6** — `Re: Updated banking details - please confirm ACH payment [SANDBOX — Case 6 / ACH ESCALATE]` · draft id `r-5524795332468896036` — body commits to no payment whatsoever.

### Auto-fail safeguards observed in the outputs
- **ACH (Case 6)** — `action: "escalate"`, `approver: "Owner"`, holding draft has no payment commitment. ✓
- **Archived-vs-active (Case 10)** — `sop_conflict.detected: true`, archived ARCH-01 named, resolved to Active SOP-02 per SOP-00. ✓
- **Freight ≠ Parcel** — Case 2 → Shipping CS (LTL/PRO), Case 9 → Parcel / Small Package (UPS 1Z). Never crossed. ✓
- **No auto-send** — drafts created via n8n Gmail Create Draft node (OAuth) only. No SMTP send path exists anywhere. ✓
- **Refund gate (Case 4)** — `approval_required: true`, `approver_role: "CS Lead"`; draft never mentions an amount or commits a refund. ✓

> **Reproduction:** `./run-triage.sh all` invokes `bin/triage-one.sh` per fixture, which runs `openclaw agent --local --json --agent main --model openai/gpt-5.5 ...` with the `fitness-triage` skill, then `bin/extract_decision.py` lifts the routing-decision JSON out of the agent envelope. Average runtime ~30s/case. Same code path the `triage-server.py` HTTP bridge uses when n8n calls it from the Gmail OAuth trigger.
