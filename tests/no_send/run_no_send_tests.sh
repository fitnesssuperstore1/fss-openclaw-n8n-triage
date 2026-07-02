#!/usr/bin/env bash
# Negative (and positive) test suite for scripts/verify_no_send.sh.
#
# Proves the no-send guard FAILS (exit 1) on any workflow that contains a
# Send / Reply / Forward / SMTP / Slack-send-style node, and PASSES (exit 0) on
# send-free workflows (draft-only + the real exports). Exits 0 only when every
# case behaves as expected.
#
#   bash tests/no_send/run_no_send_tests.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
V="$ROOT/scripts/verify_no_send.sh"
fail=0

check() {  # <expected_exit> <file>
  bash "$V" "$2" >/dev/null 2>&1; local rc=$?
  if [ "$rc" -eq "$1" ]; then
    printf "  OK    exit %s (want %s)  %s\n" "$rc" "$1" "$(basename "$2")"
  else
    printf "  FAIL  exit %s (want %s)  %s\n" "$rc" "$1" "$(basename "$2")"; fail=1
  fi
}

echo "UNSAFE fixtures — verify_no_send MUST fail (exit 1):"
for f in "$HERE"/unsafe_*.json; do check 1 "$f"; done

echo "SAFE workflows — verify_no_send MUST pass (exit 0):"
for f in "$HERE"/safe_*.json "$ROOT"/n8n/workflows/*.json; do check 0 "$f"; done

echo "----------------------------------------------------------------------"
if [ "$fail" -eq 0 ]; then
  echo "ALL AS EXPECTED — the no-send guard catches every send/reply/forward/slack node."
else
  echo "SOME CASES BEHAVED UNEXPECTEDLY — see FAIL lines above."
fi
exit "$fail"
