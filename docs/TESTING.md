# Testing

How to run the test set, add new test cases, and read the results.

---

## What "fixtures" are

A **fixture** is one fake test email saved as a JSON file under `fixtures/`.
Each fixture has the shape:

```json
{
  "case_id": "case01",
  "from": "dana.coleman@example.com",
  "to": "sales@frenchfitness.com",
  "subject": "When will my functional trainer ship?",
  "body": "Hi, I ordered…",
  "received_at": "2026-06-10T09:15:00Z",
  "expected_outcome": {
    "in_scope": false,
    "scope_label": "gorgias_owned",
    "primary_lane": null,
    "action": "out_of_scope",
    "approver_role": null,
    "notes": "Customer-facing email correctly blocked at scope_gate."
  }
}
```

Fixtures are deliberately self-contained — same shape as what n8n's
Normalize node produces for a real email — so feeding one to the chain
exercises the exact same code path as a real Gmail trigger event.

Two families:

- **`fixtures/caseNN.json`** — the original 10 cases from the brief.
  Mostly customer-facing emails sent to Gorgias-owned inboxes. Under
  Milestone 1's scope_gate, most of these correctly produce
  `action: "out_of_scope"`.
- **`fixtures/internal_*.json`** — 5 new internal/leadership cases written
  for Milestone 1. These pass scope_gate and exercise the full chain
  end-to-end.

Both families have the same shape and are loaded the same way.

---

## Running fixtures

### Build the SOP bundle once (per session)

The chain expects a SOP catalog JSON file as its second argument. n8n
normally builds this from Drive; for local fixture runs, build it from the
on-disk `sops/` tree:

```bash
python3 - <<'PY'
import json, pathlib, re
sops=[]
for d, status in [("sops/active","Active"),("sops/reference","Reference"),("sops/archived","Archived")]:
    for f in sorted(pathlib.Path(d).glob("*.md")):
        m=re.match(r'^((?:SOP|REF|ARCH)-\d{2})', f.name)
        sops.append({"id": m.group(1) if m else None, "name": f.name, "status": status, "content": f.read_text()})
pathlib.Path('/tmp/test-sops.json').write_text(json.dumps(sops))
print(f"wrote {len(sops)} SOPs to /tmp/test-sops.json")
PY
```

### Run a single fixture

```bash
python3 bin/triage-chain.py fixtures/case07.json /tmp/test-sops.json
```

The chain prints the decision JSON to stdout, with per-skill trace lines on
stderr like:

```
[chain] scope_gate (openai/gpt-5.4) -> {"in_scope": true, ...}
[chain] classify_email (openai/gpt-5.4) -> {"primary_lane": ...}
...
```

### Run all 15 fixtures

```bash
bash scripts/run_all_fixtures.sh
```

This saves each decision to `/tmp/runs/<fixture-name>.decision.json` and
each per-fixture stderr to `/tmp/runs/<fixture-name>.stderr`, then prints
a one-line summary per fixture (action, lane, sop, approver, schema errs).

### Read the output

For any individual fixture:

```bash
python3 -c "
import json
d = json.load(open('/tmp/runs/case07.decision.json'))
print(f\"action:        {d.get('action')}\")
print(f\"lane:          {d.get('primary_lane')}\")
print(f\"sop:           {(d.get('controlling_sop') or {}).get('id')}\")
print(f\"approver:      {d.get('approver_role') or d.get('route_to')}\")
print(f\"draft created: {bool(d.get('draft'))}\")
print(f\"schema errors: {len(d.get('schema_errors') or [])}\")
"
```

---

## The `expected_outcome` convention

Every fixture has an `expected_outcome` block with the field-by-field
expectation for that fixture's decision. The intent is that a regression
script can diff the actual decision against the expected and produce a
pass/fail per fixture without human reading.

The fields:

- `in_scope` (boolean) — what scope_gate should decide
- `scope_label` (string|null) — gorgias_owned / unknown / internal /
  leadership / or null when the chain went past scope_gate
- `primary_lane` (string|null) — what classify_email should decide;
  null when the chain terminated at scope_gate
- `action` (string) — draft / escalate / route / out_of_scope
- `approver_role` (string|null) — CS Lead / Ops Manager / Owner / null
- `controlling_sop` (string|null) — e.g. "SOP-04"; optional
- `route_to` (string|null) — only when action == route
- `notes` (string) — free-text explaining the expected behaviour

Field-by-field assertion semantics:

- If a field is `null` in `expected_outcome`, the actual decision's field
  should also be null (or missing).
- If a field is present and non-null, the actual decision's field should
  match exactly.
- Fields the actual decision has that aren't in `expected_outcome` are
  ignored (so adding new decision fields doesn't break old fixtures).

When the chain's behaviour intentionally changes (e.g. we added a meta-
question rule to classify_email that made internal_02 escalate instead of
draft into Shipping CS), update `expected_outcome` in that fixture to
match the new desired behaviour. Document the rationale in the fixture's
`notes` field.

---

## Adding a new test case

1. Decide what the case tests. Examples: "customer asks about pre-purchase
   financing using the wrong inbox" or "internal team forwards a vendor
   ACH escalation to leadership@".
2. Pick a file name: `fixtures/caseNN.json` for customer-facing cases,
   `fixtures/internal_NN_<short_desc>.json` for internal cases.
3. Write the fixture using the shape above. Include:
   - A realistic `from` and `to` so scope_gate can do its job.
   - A `received_at` ISO timestamp (any recent date is fine).
   - An `expected_outcome` block. If you're unsure what the chain will
     produce, run it through the chain once, inspect the decision, and
     paste in the actual outcome — then sanity-check it manually before
     committing.
4. Run `bash scripts/run_all_fixtures.sh` and verify the new fixture
   produces the expected decision.
5. Add a one-line description in `docs/TESTING.md`'s case list (below).
   Commit both the fixture and the doc update together.

---

## The 15 cases (current state)

### Original 10 (mostly customer-facing — should be blocked by scope_gate)

| File | What it tests | Expected outcome |
|---|---|---|
| case01.json | Customer ETA on an unshipped order | out_of_scope (gorgias_owned) |
| case02.json | Customer needs freight redelivery | out_of_scope (gorgias_owned) |
| case03.json | Customer asks for delivery + install | out_of_scope (gorgias_owned) |
| case04.json | Customer demands refund for damage | out_of_scope (gorgias_owned) |
| case05.json | Customer asks pre-purchase financing | out_of_scope (gorgias_owned) |
| case06.json | Vendor ACH wire request to accounts@ | out_of_scope (unknown — external sender to internal accounts inbox; scope_gate requires internal sender for rule 3) |
| case07.json | Internal warehouse staff: product page wrong | route to Product Lead (passes scope_gate as internal) |
| case08.json | Customer Gorgias-vs-Gmail conflict | out_of_scope (gorgias_owned) |
| case09.json | Customer parcel marked delivered but missing | out_of_scope (gorgias_owned) |
| case10.json | Customer freight + archived SOP conflict | out_of_scope (gorgias_owned) |

### New 5 internal/leadership (added in Milestone 1)

| File | What it tests | Expected outcome |
|---|---|---|
| internal_01_sop_question.json | Tim asks which SOP controls vendor onboarding | escalate → Ops Manager |
| internal_02_process_ownership.json | Arvin asks who owns the Shipping CS Monday board | draft → CS Lead (under SOP-08, post Rule 2 fix) |
| internal_03_gorgias_vs_internal.json | Ops asks the scope meta-question | draft → CS Lead (under SOP-08, post Rule 2 fix) |
| internal_04_leadership_ach.json | Vendor ACH sent to leadership@ | out_of_scope (unknown) under strict scope_gate; **flagged as doc inconsistency** — see fixture's `doc_intent` field |
| internal_05_internal_cleanup.json | Internal cleanup task on product specs | route → Product Lead |

---

## Regression playbook

When you change a skill prompt, schema, or chain rule:

1. Run all 15 fixtures: `bash scripts/run_all_fixtures.sh`.
2. For each fixture, diff the actual decision against `expected_outcome`.
3. Any mismatch is either: (a) the change introduced a regression, or
   (b) the change deliberately fixed a behaviour and `expected_outcome`
   needs updating. Decide which, then act.
4. Confirm `schema_errors` is empty across all 15. A non-empty
   `schema_errors` is always a bug — the AI returned malformed output and
   the chain caught it, which is correct behaviour, but it means the
   prompt needs tightening or the schema needs loosening.

When you add a new SOP file under `sops/`:

1. Make sure the filename starts with `SOP-NN`, `REF-NN`, or `ARCH-NN`.
2. Run a fixture that should now route through the new SOP and confirm
   `select_sop` picks it.
3. If `select_sop` doesn't pick it, the prompt's SOP catalog is stale —
   either the SOP is not in the right `sops/{active,reference,archived}/`
   subdirectory, or the lane in the SOP frontmatter doesn't match what
   `classify_email` would return.

When you add or rename a Monday column / group:

1. Update the column id in `.env` and `config/env.sh`.
2. If groups changed, update `config/monday-groups.json`.
3. Run any in-scope fixture and verify the card lands in the correct
   group with the correct columns set.
