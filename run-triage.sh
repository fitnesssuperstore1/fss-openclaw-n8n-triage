#!/usr/bin/env bash
# Run the OpenClaw fitness-triage skill over one or all case fixtures via
# bin/triage-one.sh (which handles key selection + model + session).
# Writes each routing-decision JSON to out/<name>.decision.json.
set -uo pipefail
ROOT="$HOME/Arvin"
OUTDIR="$ROOT/out"; mkdir -p "$OUTDIR"

run_one() {
  local f="$1"
  local name; name="$(basename "$f" .json)"
  echo "============ $name ============"
  if bash "$ROOT/bin/triage-one.sh" "$f" > "$OUTDIR/$name.decision.json" 2> "$OUTDIR/$name.err"; then
    if jq -e . "$OUTDIR/$name.decision.json" >/dev/null 2>&1; then
      jq -r '"  lane=\(.primary_lane)\n  sop=\(.controlling_sop.id) (\(.controlling_sop.status))\n  action=\(.action)  approval=\(if .approval_required then .approver_role else "none" end)  conf=\(.confidence)\n  conflict=\(.sop_conflict.detected)"' "$OUTDIR/$name.decision.json"
      echo "  -> $OUTDIR/$name.decision.json"
    else
      echo "  ! non-JSON output (see $OUTDIR/$name.decision.json + .err)"
    fi
  else
    echo "  ! FAILED rc=$?  (see $OUTDIR/$name.err)"
  fi
}

if [ "${1:-}" = "all" ]; then
  for f in "$ROOT"/fixtures/case*.json; do run_one "$f"; done
else
  run_one "${1:?usage: run-triage.sh <fixture.json|all>}"
fi
echo; echo "Done. $(ls $OUTDIR/case*.decision.json 2>/dev/null | wc -l)/10 decision files."
