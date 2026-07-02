#!/usr/bin/env bash
# run_all_fixtures.sh
#
# Regression runner. Runs every fixture under fixtures/ through the 5-skill
# chain, saves per-fixture decision JSON + stderr to /tmp/runs/, and prints a
# summary plus a pass/fail diff against each fixture's expected_outcome.
#
# Run from the repo root:
#   bash scripts/run_all_fixtures.sh
#
# Exit code:
#   0 — every fixture was ASSERTED and its decision matched expectations
#   1 — at least one fixture mismatched, hard-errored, or declared NO expectation
#       (B7: a fixture with no expected_outcome AND no expected_lane is a failure,
#        not a silent skip)
#   2 — environment problem (missing chain script, missing fixtures dir, etc.)
#
# Env vars honored:
#   FIXTURES_DIR   default: fixtures
#   RUNS_DIR       default: /tmp/runs
#   SOPS_FILE      default: build from sops/ tree
#   CHAIN_BIN      default: bin/triage-chain.py

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURES_DIR="${FIXTURES_DIR:-$REPO_ROOT/fixtures}"
RUNS_DIR="${RUNS_DIR:-/tmp/runs}"
CHAIN_BIN="${CHAIN_BIN:-$REPO_ROOT/bin/triage-chain.py}"

if [ ! -d "$FIXTURES_DIR" ]; then
  echo "ERROR: fixtures directory not found at $FIXTURES_DIR" >&2; exit 2
fi
if [ ! -f "$CHAIN_BIN" ]; then
  echo "ERROR: triage-chain.py not found at $CHAIN_BIN" >&2; exit 2
fi

mkdir -p "$RUNS_DIR"

# --------------------------------------------------------------------------
# Build the SOP bundle from on-disk sops/. n8n normally does this from Drive;
# for local regression we build the same shape from the markdown files.
# --------------------------------------------------------------------------
SOPS_FILE="${SOPS_FILE:-$RUNS_DIR/sops.json}"
python3 - "$REPO_ROOT" "$SOPS_FILE" <<'PY'
import json, pathlib, re, sys
repo = pathlib.Path(sys.argv[1])
out  = pathlib.Path(sys.argv[2])
sops = []
for d, status in [("sops/active", "Active"),
                  ("sops/reference", "Reference"),
                  ("sops/archived", "Archived")]:
    p = repo / d
    if not p.exists():
        continue
    for f in sorted(p.glob("*.md")):
        m = re.match(r'^((?:SOP|REF|ARCH)-\d{2})', f.name)
        sops.append({
            "id":     m.group(1) if m else None,
            "name":   f.name,
            "status": status,
            "content": f.read_text(),
        })
out.write_text(json.dumps(sops))
print(f"sops bundle: {len(sops)} SOPs written to {out}", file=sys.stderr)
PY
if [ $? -ne 0 ]; then
  echo "ERROR: failed to build sops bundle" >&2; exit 2
fi

# --------------------------------------------------------------------------
# Run each fixture
# --------------------------------------------------------------------------
fixtures=()
while IFS= read -r f; do fixtures+=("$f"); done < <(find "$FIXTURES_DIR" -maxdepth 1 -name '*.json' | sort)
total=${#fixtures[@]}
if [ "$total" -eq 0 ]; then
  echo "ERROR: no fixtures found under $FIXTURES_DIR" >&2; exit 2
fi

echo ""
echo "Running $total fixture(s) through the chain. Outputs in $RUNS_DIR/"
echo ""

passed=0
failed=0
errored=0
results=()

for f in "${fixtures[@]}"; do
  name=$(basename "$f" .json)
  dec="$RUNS_DIR/${name}.decision.json"
  err="$RUNS_DIR/${name}.stderr"
  start=$(date +%s)
  # B7: case* fixtures carry a top-level expected_lane and are engine-regression
  # cases — run them with SKIP_SCOPE_GATE=1 so the engine classifies a lane
  # instead of scope_gate short-circuiting them to out_of_scope. In-scope
  # fixtures (expected_outcome.*) run normally through the gate.
  skip_env=""
  if python3 -c "import json,sys; sys.exit(0 if json.load(open('$f')).get('expected_lane') else 1)"; then
    skip_env="SKIP_SCOPE_GATE=1"
  fi
  if ! env $skip_env python3 "$CHAIN_BIN" "$f" "$SOPS_FILE" > "$dec" 2> "$err"; then
    elapsed=$(($(date +%s) - start))
    echo "  ✗ $name  ERRORED in ${elapsed}s — see $err"
    errored=$((errored + 1))
    results+=("$name ERRORED")
    continue
  fi
  elapsed=$(($(date +%s) - start))

  # diff actual decision against expected_outcome
  diff_result=$(python3 - "$f" "$dec" <<'PY'
import json, sys
fix = json.load(open(sys.argv[1]))
dec = json.load(open(sys.argv[2]))
exp = fix.get("expected_outcome", {}) or {}
exp_lane = fix.get("expected_lane")

# B7: a fixture with NO assertions (no expected_outcome AND no expected_lane) is
# a HARD FAILURE — the runner must never silently skip / pass an unasserted case.
if not exp and exp_lane is None:
    print("NO_EXPECTATION — fixture declares no expected_outcome or expected_lane")
    sys.exit(2)

mismatches = []
def check(field, actual):
    if field in exp and exp[field] != actual:
        mismatches.append(f"{field}: expected {exp[field]!r}, got {actual!r}")

check("action",        dec.get("action"))
check("scope_label",   dec.get("scope_label"))
check("primary_lane",  dec.get("primary_lane"))
check("approver_role", dec.get("approver_role"))
check("route_to",      dec.get("route_to"))
# controlling_sop in expected_outcome is just the SOP id string
if "controlling_sop" in exp:
    actual_sop = (dec.get("controlling_sop") or {}).get("id")
    if exp["controlling_sop"] != actual_sop:
        mismatches.append(f"controlling_sop: expected {exp['controlling_sop']!r}, got {actual_sop!r}")
# B7: top-level expected_lane asserted against the decision's primary_lane.
if exp_lane is not None and dec.get("primary_lane") != exp_lane:
    mismatches.append(f"expected_lane: expected {exp_lane!r}, got {dec.get('primary_lane')!r}")
# schema_errors must always be empty
serr = dec.get("schema_errors") or []
if serr:
    mismatches.append(f"schema_errors not empty: {serr}")

if mismatches:
    print("MISMATCH")
    for m in mismatches:
        print("  -", m)
    sys.exit(1)
print("OK")
PY
  )
  rc=$?
  if [ $rc -eq 0 ]; then
    echo "  ✓ $name  (${elapsed}s)  $(echo "$diff_result" | head -1)"
    passed=$((passed + 1))
    results+=("$name PASS")
  else
    echo "  ✗ $name  (${elapsed}s)  $(echo "$diff_result" | head -1)"
    echo "$diff_result" | tail -n +2 | sed 's/^/        /'
    failed=$((failed + 1))
    results+=("$name FAIL")
  fi
done

echo ""
echo "----------------------------------------------------------------------"
echo "Summary:  $passed passed | $failed failed | $errored errored | total $total"
echo "Outputs:  $RUNS_DIR/"
echo "----------------------------------------------------------------------"

if [ "$failed" -gt 0 ] || [ "$errored" -gt 0 ]; then
  exit 1
fi
exit 0
