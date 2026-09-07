#!/usr/bin/env python3
"""Focused, deterministic tests for the internal-governance routing path.

Every source used here is the EXACT repository document — sops/active/SOP-08,
sops/reference/REF-03, sops/reference/REF-04 are read from disk, never a
substitute or an expanded string. Tests that need a broken source derive it from
the real one (delete it, flip its status, blank it, or duplicate/conflict it).

The four skill calls are stubbed so every assertion is on the chain's own
deterministic logic: source resolution, fail-closed escalation, the strict
validated audit gate, and draft-body grounding. No model, no API credits.

  python3 tests/internal_governance/test_governance_gates.py

Exit 0 = all passed, 1 = a failure.
"""
import copy, io, json, pathlib, re, sys
from contextlib import redirect_stdout, redirect_stderr

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin"))
import importlib.util
spec = importlib.util.spec_from_file_location("tc", ROOT / "bin" / "triage-chain.py")
tc = importlib.util.module_from_spec(spec); spec.loader.exec_module(tc)
from sop_source import InMemorySopSource

# ---------------------------------------------------------------------------
# THE REAL REPOSITORY SOURCE PACKET (identical to what the runner builds)
# ---------------------------------------------------------------------------
def repo_packet():
    docs = []
    for sub, status in [("sops/active", "Active"), ("sops/reference", "Reference"),
                        ("sops/archived", "Archived")]:
        d = ROOT / sub
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            m = re.match(r"^((?:SOP|REF|ARCH)-\d{2})", f.name)
            docs.append({"id": m.group(1) if m else None, "name": f.name,
                         "status": status, "content": f.read_text()})
    return docs

REPO_DOCS = repo_packet()
SOP08_TEXT = next(d["content"] for d in REPO_DOCS if d["id"] == "SOP-08")


def source(docs=None):
    return InMemorySopSource(copy.deepcopy(docs if docs is not None else REPO_DOCS))


def without(doc_id):
    return [d for d in copy.deepcopy(REPO_DOCS) if d["id"] != doc_id]


def mutate(doc_id, **changes):
    docs = copy.deepcopy(REPO_DOCS)
    for d in docs:
        if d["id"] == doc_id:
            d.update(changes)
    return docs


def duplicate(doc_id, **changes):
    """Add a SECOND document with the same id (duplicate / conflicting source)."""
    docs = copy.deepcopy(REPO_DOCS)
    orig = next(d for d in docs if d["id"] == doc_id)
    dup = copy.deepcopy(orig)
    dup.update(changes)
    docs.append(dup)
    return docs


def classify_out(lane="Escalate / Needs Human Review"):
    return {"primary_lane": lane, "secondary_lane": None, "confidence": 94,
            "reasoning": "internal governance meta-question", "signals": ["internal"],
            "is_internal": True}


def draft_out(body, subject="Re: your question", approver="CS Lead"):
    return {"draft_subject": subject, "draft_body": body, "approval_required": True,
            "approver_role": approver, "tone_notes": "internal note; factual and brief",
            "uncommitted_items": []}


AUDIT_PASS = {"pass": True, "violations": [], "force_escalate": False,
              "escalation_reason": None, "notify_role": None}
AUDIT_FAIL = {"pass": False, "violations": ["draft promises a refund"], "force_escalate": True,
              "escalation_reason": "draft makes an unsupported promise", "notify_role": "CS Lead"}
AUDIT_MALFORMED = {"pass": "yes", "force_escalate": "no"}                 # wrong types
AUDIT_EMPTY = {"pass": None, "force_escalate": None}                       # missing/empty
AUDIT_CONTRADICTORY = {"pass": True, "violations": ["found a promise"], "force_escalate": True,
                       "escalation_reason": None, "notify_role": None}     # fields disagree
AUDIT_NONKEYWORD = {"pass": False, "violations": ["tone is inappropriate for the audience"],
                    "force_escalate": True, "escalation_reason": "tone unsuitable",
                    "notify_role": "CS Lead"}                              # rejection w/o keyword


def run(email, src, draft=None, audit=AUDIT_PASS, capture=None, audit_raises=False):
    """Run run_engine with stubbed skills; return the emitted decision dict."""
    def fake_call_skill(skill_name, payload, tag):
        if capture is not None:
            capture.setdefault(skill_name, []).append(json.loads(payload))
        if skill_name == "classify_email":
            return classify_out()
        if skill_name == "draft_response":
            return draft
        if skill_name == "audit_check":
            if audit_raises:
                raise RuntimeError("audit_check unreachable")
            return audit
        raise AssertionError("unexpected skill: " + skill_name)

    orig = tc.call_skill
    tc.call_skill = fake_call_skill
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            tc.run_engine(email, src, [], "test", scope_label="internal")
    finally:
        tc.call_skill = orig
    out = buf.getvalue().strip()
    return json.loads(out) if out else {}


PROC = {"from": "ops.director@frenchfitness.com", "to": "leadership@frenchfitness.com",
        "subject": "Process ownership", "body": "Who currently owns the Shipping CS Monday board?"}
SUPP = {"from": "ops.analyst@frenchfitness.com", "to": "ops@frenchfitness.com",
        "subject": "Scope question",
        "body": "Does this freight-delay go through internal Gmail triage or is it fully Gorgias-owned?"}
SOPQ = {"from": "ops.coordinator@frenchfitness.com", "to": "team@frenchfitness.com",
        "subject": "Which SOP controls onboarding",
        "body": "Which SOP do we follow for vendor onboarding governance right now?"}

# A neutral holding reply: acknowledges, promises nothing, claims no owner/channel.
NEUTRAL = ("Hi,\n\nThanks for flagging this. I don't have a confirmed answer to give you yet, so I'm "
           "routing your question to the right reviewer and will follow up once they confirm.\n\n"
           "Thanks,\nOperations")

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# ===========================================================================
# A. GROUNDING against the REAL repository sources
# ===========================================================================
# A1 — the real SOP-08 is what gets handed to the drafting model (byte-identical)
cap = {}
d = run(PROC, source(), draft=draft_out(NEUTRAL), capture=cap)
handed = (cap.get("draft_response") or [{}])[0].get("sop_content", "")
check("A1 drafting model receives the EXACT repository SOP-08",
      handed == SOP08_TEXT and d.get("action") == "draft_pending_approval",
      f"identical={handed == SOP08_TEXT} action={d.get('action')}")

# A2 — the real SOP-08 genuinely does NOT name a board owner (guards the tests themselves)
check("A2 repository SOP-08 does not identify the Shipping CS board owner",
      not re.search(r"(?i)monday board.*(owner|owned by)|board owner", SOP08_TEXT))

# A3 — NEGATIVE: an unsupported OWNERSHIP answer cannot become a draft
d = run(PROC, source(), draft=draft_out(
    "Hi,\n\nThe Shipping CS Monday board is owned by the Logistics Desk; contact them for access.\n\nThanks"))
check("A3 unsupported ownership claim -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None,
      str(d.get("escalation_reason"))[:60])

# A4 — NEGATIVE: an unsupported CHANNEL-ROUTING answer cannot become a draft
d = run(SUPP, source(), draft=draft_out(
    "Hi,\n\nThat freight delay belongs in the Gorgias / Shipping CS workflow, not internal triage.\n\nThanks"))
check("A4 unsupported channel-routing claim -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None,
      str(d.get("escalation_reason"))[:60])

# A5 — a NEUTRAL holding reply (no ownership/channel claim) is allowed to draft
d = run(PROC, source(), draft=draft_out(NEUTRAL))
body = (d.get("draft") or {}).get("body", "")
check("A5 neutral holding reply (no claim) -> draft_pending_approval / Ops Manager",
      d.get("action") == "draft_pending_approval" and d.get("approver_role") == "Ops Manager"
      and not tc._OWNERSHIP_CLAIM_RX.search(body), str(d.get("action")))

# A6 — the engine never appends a business conclusion the source doesn't state
d = run(SUPP, source(), draft=draft_out(NEUTRAL))
body = (d.get("draft") or {}).get("body", "")
unc = " ".join(d.get("uncommitted_items") or [])
check("A6 engine does not append a Gorgias/Shipping-CS conclusion to body or items",
      "gorgias" not in body.lower() and "gorgias" not in unc.lower(),
      (body[-40:] + " | " + unc[:40]))

# ===========================================================================
# B. STRICT, VALIDATED, FAIL-CLOSED AUDIT GATE
# ===========================================================================
for label, kwargs in [
    ("malformed audit output (wrong types)", {"audit": AUDIT_MALFORMED}),
    ("empty audit output (missing fields)", {"audit": AUDIT_EMPTY}),
    ("contradictory audit fields", {"audit": AUDIT_CONTRADICTORY}),
    ("non-keyword audit rejection", {"audit": AUDIT_NONKEYWORD}),
    ("keyword audit rejection", {"audit": AUDIT_FAIL}),
    ("audit_check unreachable", {"audit_raises": True}),
]:
    d = run(PROC, source(), draft=draft_out(NEUTRAL), **kwargs)
    check(f"B {label} -> escalate, draft=null",
          d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# B7 — the deterministic auditor blocks a promise even if the model audit passes
d = run(PROC, source(), draft=draft_out(
    "Hi,\n\nWe will refund you $500 today and replace the unit this week.\n\nThanks"), audit=AUDIT_PASS)
check("B7 no-promise violation blocked even when model audit says pass",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# B8 — internal metadata (SOP id) blocked by the schema/auditor
d = run(PROC, source(), draft=draft_out(
    "Hi,\n\nPer SOP-08 I'll route this to the right reviewer and follow up shortly.\n\nThanks"))
check("B8 internal metadata (SOP id) -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# B9 — a trailing internal footer is stripped and never reaches the final draft
d = run(PROC, source(), draft=draft_out(
    NEUTRAL + "\n\n[DRAFT — pending human approval | lane: Escalate / Needs Human Review | SOP: SOP-08 (Active)]"))
fb = (d.get("draft") or {}).get("body", "")
check("B9 internal footer stripped from the final draft",
      d.get("action") == "draft_pending_approval" and "[DRAFT" not in fb and "SOP-08" not in fb,
      fb[-40:])

# ===========================================================================
# C. MISSING / NON-ACTIVE / EMPTY sources -> fail closed
# ===========================================================================
for label, docs in [
    ("REF-03 missing", without("REF-03")),
    ("REF-04 missing", without("REF-04")),
    ("SOP-08 missing", without("SOP-08")),
    ("SOP-08 non-Active", mutate("SOP-08", status="Reference")),
    ("SOP-08 empty content", mutate("SOP-08", content="   ")),
]:
    d = run(PROC, source(docs), draft=draft_out(NEUTRAL))
    check(f"C {label} -> escalate, draft=null",
          d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# ===========================================================================
# D. DUPLICATE / CONFLICTING sources -> fail closed
# ===========================================================================
# D1 — duplicate REF-03 whose mapping CONFLICTS (process_ownership -> CS Lead)
conflict_routing = SOP08_TEXT  # placeholder replaced below
dup_ref03 = duplicate("REF-03", name="REF-03_Unified_Routing_SOP_COPY.md",
                      content="- process_ownership: CS Lead\n- support_channel: Ops Manager\n")
d = run(PROC, source(dup_ref03), draft=draft_out(NEUTRAL))
check("D1 conflicting duplicate REF-03 mapping -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# D2 — duplicate REF-03 that AGREES is not a conflict (must still work)
dup_ref03_same = duplicate("REF-03", name="REF-03_Unified_Routing_SOP_COPY.md")
d = run(PROC, source(dup_ref03_same), draft=draft_out(NEUTRAL))
check("D2 duplicate-but-identical REF-03 still resolves -> draft_pending_approval",
      d.get("action") == "draft_pending_approval", str(d.get("action")))

# D3 — duplicate REF-04 with a CONFLICTING holder for the same role
dup_ref04 = duplicate("REF-04", name="REF-04_Org_Chart_COPY.md",
                      content="| Ops Manager | someone-else@frenchfitness.com |\n")
d = run(PROC, source(dup_ref04), draft=draft_out(NEUTRAL))
check("D3 conflicting duplicate REF-04 holder -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# D4 — ambiguous holder rows inside ONE REF-04 (two mailboxes for a role)
amb = mutate("REF-04", content=next(d2["content"] for d2 in REPO_DOCS if d2["id"] == "REF-04")
             + "\n| Ops Manager | ops-manager-2@frenchfitness.com |\n")
d = run(PROC, source(amb), draft=draft_out(NEUTRAL))
check("D4 ambiguous holder rows -> escalate (never first-match)",
      d.get("action") == "escalate" and d.get("draft") is None
      and "ambiguous" in (d.get("escalation_reason") or "").lower(),
      str(d.get("escalation_reason"))[:60])

# D5 — duplicate SOP-08 with CONFLICTING content
dup_sop = duplicate("SOP-08", name="SOP-08_Support_Channel_Conflict_COPY.md",
                    content="Channel disagreement is auto-resolved by the system; no escalation needed.")
d = run(SUPP, source(dup_sop), draft=draft_out(NEUTRAL))
check("D5 conflicting duplicate SOP-08 -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# ===========================================================================
# E. HAPPY PATHS — role derived from the real mock routing packet
# ===========================================================================
d = run(SOPQ, source(), draft=draft_out("unused"))
check("E1 sop_governance -> escalate / Owner (draft=null)",
      d.get("action") == "escalate" and d.get("approver_role") == "Owner" and d.get("draft") is None,
      str(d.get("approver_role")))
d = run(SUPP, source(), draft=draft_out(NEUTRAL))
check("E2 support_channel -> draft_pending_approval / CS Lead",
      d.get("action") == "draft_pending_approval" and d.get("approver_role") == "CS Lead",
      str(d.get("approver_role")))

# ===========================================================================
# F. UNSUPPORTED IMPERATIVE ROUTING DIRECTIVES  (adversarial finding 1)
#    A draft may not instruct where the work goes unless the destination is
#    source-authorised. Neutral holding replies stay allowed.
# ===========================================================================
UNSUPPORTED_DIRECTIVES = [
    "Please route this to the Logistics Desk.",
    "Send it to the Shipping CS team.",
    "Forward this to the Warehouse Supervisor.",
    "Open a ticket in Gorgias for this.",
    "Please escalate this to the Fulfilment Manager.",
    "Log it in the Freight Portal.",
    "Reassign this to the Returns Desk.",
    "Create a task in Monday for the Logistics Desk.",
    # identified in Tim's second adversarial pass (SHA 60d569e):
    "Use Shipping CS for this request.",
    "Please contact the Logistics team about this.",
]
for phrase in UNSUPPORTED_DIRECTIVES:
    d = run(PROC, source(), draft=draft_out(
        "Hi,\n\nThanks for checking on this. " + phrase + " Someone will confirm shortly.\n\nThanks"))
    check(f"F unsupported directive -> escalate: {phrase[:38]}",
          d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# F-compound — several directives, one of them unsupported: whole draft fails closed
d = run(PROC, source(), draft=draft_out(
    "Hi,\n\nThanks for flagging. I'm routing this for human review, and please also open a ticket in "
    "Gorgias and forward it to the Logistics Desk so they can pick it up.\n\nThanks"))
check("F compound directive (one unsupported) -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# F-neutral — a neutral holding reply naming no destination still drafts
d = run(PROC, source(), draft=draft_out(NEUTRAL))
check("F neutral holding reply still allowed -> draft_pending_approval",
      d.get("action") == "draft_pending_approval", str(d.get("action")))

# F-contact-authorised — a contact-style directive naming the source-authorised
# approver role is still allowed (guards the new "contact X" rule against
# over-blocking the neutral/authorised behaviour)
d = run(PROC, source(), draft=draft_out(
    "Hi,\n\nThanks for checking. Please contact the Ops Manager to confirm the current owner; "
    "I'll follow up once they do.\n\nThanks"))
check("F 'contact <authorised role>' still allowed -> draft_pending_approval",
      d.get("action") == "draft_pending_approval" and d.get("approver_role") == "Ops Manager",
      str(d.get("action")))

# F-noun-contact — "contact" used as a NOUN (a real model-produced sentence from a
# previous live internal_02 run) must not be mistaken for a directive
d = run(PROC, source(), draft=draft_out(
    "Hi,\n\nThanks for checking. I'm not going to assume ownership from a single thread, so I'm "
    "routing this for human review. A reviewer will follow up with the right contact or document "
    "if available.\n\nThanks"))
check("F 'the right contact or document' (noun) is not a directive -> draft_pending_approval",
      d.get("action") == "draft_pending_approval", str(d.get("escalation_reason"))[:60])

# F-authorised — routing to the approver role the routing source itself selected
d = run(SUPP, source(), draft=draft_out(
    "Hi,\n\nThanks for flagging this. I'm sending it to the CS Lead to review both sides before "
    "anyone replies to the customer.\n\nThanks"))
check("F routing to the source-authorised approver role still allowed",
      d.get("action") == "draft_pending_approval" and d.get("approver_role") == "CS Lead",
      str(d.get("action")))

# ===========================================================================
# G. SAME-ID SOURCE CONFLICTS  (adversarial finding 2)
#    Identity is the canonical document ID — a conflicting copy cannot hide
#    behind a different filename or title.
# ===========================================================================
for label, doc_id, changes in [
    ("REF-03 same id, different filename+content", "REF-03",
     dict(name="routing-v2-final.md", title="Routing v2", content="- process_ownership: CS Lead\n")),
    ("REF-04 same id, different filename+content", "REF-04",
     dict(name="people-directory.md", title="People", content="| Ops Manager | someone-else@frenchfitness.com |\n")),
    ("SOP-08 same id, different filename+content", "SOP-08",
     dict(name="support-policy-old.md", title="Support Policy",
          content="Channel disagreement is auto-resolved; no escalation needed.")),
]:
    d = run(PROC if doc_id != "SOP-08" else SUPP, source(duplicate(doc_id, **changes)),
            draft=draft_out(NEUTRAL))
    check(f"G {label} -> escalate, draft=null",
          d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# G-identical — same id, different filename, IDENTICAL content is not a conflict
same = duplicate("REF-03", name="unified-routing-copy.md", title="Routing copy")
d = run(PROC, source(same), draft=draft_out(NEUTRAL))
check("G same id + different filename but identical content still resolves",
      d.get("action") == "draft_pending_approval", str(d.get("action")))

# ===========================================================================
# H. CONFLICTING MAPPINGS INSIDE ONE REF-03  (adversarial finding 3)
# ===========================================================================
ref03_text = next(x["content"] for x in REPO_DOCS if x["id"] == "REF-03")
d = run(PROC, source(mutate("REF-03", content=ref03_text + "\n- process_ownership: CS Lead\n")),
        draft=draft_out(NEUTRAL))
check("H same domain mapped to two roles in one REF-03 -> escalate, draft=null",
      d.get("action") == "escalate" and d.get("draft") is None
      and "ambiguous" in (d.get("escalation_reason") or "").lower(),
      str(d.get("escalation_reason"))[:60])

# H-dedupe — an identical repeated mapping line is deduplicated, not a conflict
d = run(PROC, source(mutate("REF-03", content=ref03_text + "\n- process_ownership: Ops Manager\n")),
        draft=draft_out(NEUTRAL))
check("H identical duplicate mapping line is deduplicated -> draft_pending_approval",
      d.get("action") == "draft_pending_approval", str(d.get("action")))

# H-direct — load_routing_map itself reports ambiguity via the sentinel
amb_map = tc.load_routing_map(source(mutate("REF-03", content="- support_channel: CS Lead\n- support_channel: Owner\n")))
ok_map = tc.load_routing_map(source())
check("H load_routing_map flags ambiguity and still parses a clean source",
      tc.ROUTING_AMBIGUOUS in amb_map and ok_map.get("process_ownership") == "Ops Manager",
      f"amb={amb_map} ok={ok_map.get('process_ownership')}")

# --- report ---
print("\nInternal-governance gate tests (against the REAL repository sources)")
print("-" * 72)
passed = 0
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if not ok and detail else ""))
    passed += ok
print("-" * 72)
print(f"{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
