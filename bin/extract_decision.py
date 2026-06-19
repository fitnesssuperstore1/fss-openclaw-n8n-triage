#!/usr/bin/env python3
"""Extract the routing-decision JSON from an OpenClaw agent
`--json` envelope (whose exact shape can vary). Robust: walks the envelope
looking for any dict (or JSON-string) that contains "primary_lane".

Usage: extract_decision.py <openclaw_envelope.json>
Prints the decision JSON to stdout; exits non-zero if none found.
"""
import json, sys, re

REQUIRED_KEY = "primary_lane"

def candidates(obj):
    """Yield dicts/decodable strings found anywhere in the structure."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from candidates(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from candidates(v)
    elif isinstance(obj, str):
        s = obj.strip()
        # strip markdown code fences if present
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.MULTILINE).strip()
        if REQUIRED_KEY in s:
            # try whole string, then the first {...} block
            for cand in (s, _first_json_object(s)):
                if not cand:
                    continue
                try:
                    parsed = json.loads(cand)
                    yield parsed
                    yield from candidates(parsed)
                except Exception:
                    pass

def _first_json_object(s):
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    return None

def main():
    if len(sys.argv) < 2:
        print("usage: extract_decision.py <envelope.json>", file=sys.stderr)
        sys.exit(2)
    raw = open(sys.argv[1], "r", encoding="utf-8", errors="replace").read()
    # The envelope itself should be JSON; if not, try to find a JSON block.
    env = None
    try:
        env = json.loads(raw)
    except Exception:
        blk = _first_json_object(raw)
        if blk:
            try:
                env = json.loads(blk)
            except Exception:
                env = raw
        else:
            env = raw
    for c in candidates(env):
        if isinstance(c, dict) and REQUIRED_KEY in c:
            print(json.dumps(c, indent=2))
            return
    print("ERROR: no routing-decision JSON (missing 'primary_lane') found", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
