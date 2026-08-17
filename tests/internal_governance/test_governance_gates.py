#!/usr/bin/env python3
"""Focused, deterministic tests for the internal-governance routing path.

Proves the behaviours Arvin's review (item 5) asked for, WITHOUT depending on a
live model: the four skill calls are stubbed, so every assertion is on the
chain's own deterministic logic (source resolution, fail-closed escalation, the
strict schema + audit gate, and draft-body content).

  python3 tests/internal_governance/test_governance_gates.py

Exit 0 = all passed, 1 = a failure.
"""
import io, json, os, pathlib, sys
from contextlib import redirect_stdout, redirect_stderr

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin"))
import importlib.util
spec = importlib.util.spec_from_file_location("tc", ROOT / "bin" / "triage-chain.py")
tc = importlib.util.module_from_spec(spec); spec.loader.exec_module(tc)
from sop_source import InMemorySopSource

# --- mock source packets (labelled MOCK / TEST ONLY, same shape as REF-03/04) ---
ROUTING = """- sop_governance: Owner
- process_ownership: Ops Manager
- support_channel: CS Lead
"""
ORG = """| Owner | owner@frenchfitness.com |
| Ops Manager | ops-manager@frenchfitness.com |
| CS Lead | cs-lead@frenchfitness.com |
"""
SOP08 = "SOP-08 Support Channel Conflict: internal triage owns governance questions; " \
        "customer support issues belong to the active Gorgias / Shipping CS workflow."


def make_source(routing=ROUTING, org=ORG, sop08=SOP08, sop08_status="Active"):
    docs = []
    if routing is not None:
        docs.append({"id": "REF-03", "name": "REF-03_Unified_Routing_SOP.md",
                     "status": "Reference", "content": routing})
    if org is not None:
        docs.append({"id": "REF-04", "name": "REF-04_Org_Chart.md",
                     "status": "Reference", "content": org})
    if sop08 is not None:
        docs.append({"id": "SOP-08", "name": "SOP-08_Support_Channel_Conflict.md",
                     "status": sop08_status, "content": sop08})
    return InMemorySopSource(docs)


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


def run(email, source, draft=None, audit=AUDIT_PASS, capture=None):
    """Run run_engine with stubbed skills; return the emitted decision dict."""
    def fake_call_skill(skill_name, payload, tag):
        if capture is not None:
            capture.setdefault(skill_name, []).append(json.loads(payload))
        if skill_name == "classify_email":
            return classify_out()
        if skill_name == "draft_response":
            return draft
        if skill_name == "audit_check":
            return audit
        raise AssertionError("unexpected skill: " + skill_name)

    orig = tc.call_skill
    tc.call_skill = fake_call_skill
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            tc.run_engine(email, source, [], "test", scope_label="internal")
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

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# 5a — internal_02 draft is SOURCE-GROUNDED (SOP-08 content fed to draft_response)
cap = {}
d = run(PROC, make_source(), draft=draft_out(
    "Hi,\n\nThe Shipping CS Monday board sits under our operations function; I'll confirm the "
    "current owner and follow up shortly.\n\nThanks,\nOperations"), capture=cap)
grounded = bool(cap.get("draft_response")) and SOP08[:20] in (cap["draft_response"][0].get("sop_content") or "")
check("5a process_ownership draft is grounded in SOP-08 source",
      d.get("action") == "draft_pending_approval" and grounded, str(d.get("action")))

# 5b — internal_03 states the Gorgias/Shipping CS routing in the DRAFT BODY
d = run(SUPP, make_source(), draft=draft_out(
    "Hi,\n\nThanks for flagging the routing — I'll confirm and get back to you on the internal side.\n\n"
    "Thanks,\nCS"))
body = (d.get("draft") or {}).get("body", "")
check("5b support_channel BODY names Gorgias / Shipping CS",
      d.get("action") == "draft_pending_approval" and "gorgias" in body.lower()
      and "shipping cs" in body.lower(), body[-70:])

# 5c — missing REF-03 / REF-04 / SOP-08 (and non-Active SOP-08) -> escalate, draft=null
for label, src in [
    ("missing REF-03", make_source(routing=None)),
    ("missing REF-04", make_source(org=None)),
    ("missing SOP-08", make_source(sop08=None)),
    ("non-Active SOP-08", make_source(sop08_status="Reference")),
]:
    d = run(PROC, src, draft=draft_out("Hi, some internal reply that is plenty long enough here."))
    check(f"5c {label} -> escalate + draft=null",
          d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# 5d — ambiguous role holder (two Ops Manager mailboxes) -> escalate, not first-match
amb_org = ORG + "| Ops Manager | ops-manager-2@frenchfitness.com |\n"
d = run(PROC, make_source(org=amb_org), draft=draft_out("Hi, internal reply long enough to pass."))
check("5d ambiguous holder -> escalate (not first email)",
      d.get("action") == "escalate" and d.get("draft") is None
      and "ambiguous" in (d.get("escalation_reason") or "").lower(), d.get("escalation_reason", "")[:60])

# 5e/5f — the strict SCHEMA gate fires: a draft citing an SOP id (mid-body) is rejected
d = run(PROC, make_source(), draft=draft_out(
    "Hi,\n\nPer SOP-08 the board is owned by operations; I'll confirm the owner shortly.\n\nThanks"))
check("5f schema gate fires on internal-metadata (SOP id) -> escalate",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# 5e — a trailing internal footer is stripped, never reaches the final draft
d = run(PROC, make_source(), draft=draft_out(
    "Hi,\n\nThe board is owned by operations; I'll confirm the current owner and follow up.\n\nThanks,\nOps"
    "\n\n[DRAFT — pending human approval | lane: Escalate / Needs Human Review | SOP: SOP-08 (Active)]"))
fb = (d.get("draft") or {}).get("body", "")
check("5e internal footer stripped from final draft",
      d.get("action") == "draft_pending_approval" and "[DRAFT" not in fb and "SOP-08" not in fb, fb[-50:])

# 5e/5f — the AUDIT/no-promise gate fires: audit force_escalate -> escalate, draft=null
d = run(PROC, make_source(),
        draft=draft_out("Hi,\n\nWe will refund you $500 today and replace the unit.\n\nThanks"),
        audit=AUDIT_FAIL)
check("5f audit/no-promise gate fires -> escalate + draft=null",
      d.get("action") == "escalate" and d.get("draft") is None, str(d.get("action")))

# happy paths — correct action + role derived from the mock routing source
d = run(PROC, make_source(), draft=draft_out("Hi,\n\nThe board sits with operations; confirming the owner now.\n\nThanks"))
check("process_ownership -> draft_pending_approval / Ops Manager",
      d.get("action") == "draft_pending_approval" and d.get("approver_role") == "Ops Manager", str(d.get("approver_role")))
d = run(SOPQ, make_source(), draft=draft_out("unused"))
check("sop_governance -> escalate / Owner (draft=null)",
      d.get("action") == "escalate" and d.get("approver_role") == "Owner" and d.get("draft") is None,
      str(d.get("approver_role")))

# --- report ---
print("\nInternal-governance gate tests")
print("-" * 64)
passed = 0
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if not ok and detail else ""))
    passed += ok
print("-" * 64)
print(f"{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
