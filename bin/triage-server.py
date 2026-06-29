#!/usr/bin/env python3
"""Host-side triage bridge so a containerized n8n can reach OpenClaw.

POST /triage   body shapes:
                 (legacy) {from,subject,body,...}                       — disk SOPs
                 (new)    {"email": {...}, "sops": [{id,name,status,content}, ...]}
               -> runs bin/triage-pipeline.sh (OpenClaw triage + Gmail draft +
                  Monday card) and returns the routing-decision JSON.
               If sops are provided, they are written to a sidecar JSON file
               and the pipeline embeds them in the OpenClaw prompt instead of
               having OpenClaw read /home/yoni/Arvin/sops/ off disk.
GET  /health   -> {"ok":true}

Binds 127.0.0.1:8088 (loopback only). A host-networked n8n container reaches it
at http://127.0.0.1:8088/triage. Not exposed externally.
"""
import json, os, subprocess, time, http.server, socketserver, tempfile

ROOT = os.path.expanduser("~/Arvin")
HOST, PORT = "127.0.0.1", 8088
# B5: caps on untrusted input — reject oversized requests and truncate the
# email body before it reaches the model.
MAX_REQUEST_BYTES = 512 * 1024     # 512 KB whole-request ceiling
MAX_EMAIL_BODY_CHARS = 50_000      # per-field email-body cap

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[bridge] " + (fmt % args))

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            return self._send(200, {"ok": True, "ts": time.time()})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/triage":
            return self._send(404, {"error": "not found"})
        # B5: reject oversized requests before reading the body.
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, {"error": "bad content-length"})
        if n > MAX_REQUEST_BYTES:
            return self._send(413, {"error": "payload too large"})
        try:
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
            payload = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            print("[bridge] bad json: %s" % e)       # detail stays server-side
            return self._send(400, {"error": "bad json"})

        # Accept two shapes:
        #   { email: {...}, sops: [...] }   <-- new (Drive-fed)
        #   { from, subject, body, ... }    <-- legacy (disk-fed)
        sops = None
        if isinstance(payload, dict) and "email" in payload and "sops" in payload:
            email = payload.get("email") or {}
            sops = payload.get("sops") or []
        else:
            email = payload

        # B5: cap the untrusted email body before it reaches the model.
        if isinstance(email, dict) and isinstance(email.get("body"), str):
            if len(email["body"]) > MAX_EMAIL_BODY_CHARS:
                email["body"] = email["body"][:MAX_EMAIL_BODY_CHARS] + "\n[...truncated]"

        # B6: unique, mode-0600 temp files, always cleaned up in finally.
        tmp_paths = []
        try:
            fd, email_path = tempfile.mkstemp(prefix="triage-", suffix=".json")
            tmp_paths.append(email_path)
            with os.fdopen(fd, "w") as f:
                json.dump(email, f)

            args = ["bash", os.path.join(ROOT, "bin", "triage-pipeline.sh"), email_path]
            if sops is not None:
                fd2, sops_path = tempfile.mkstemp(prefix="triage-", suffix=".sops.json")
                tmp_paths.append(sops_path)
                with os.fdopen(fd2, "w") as f:
                    json.dump(sops, f)
                args.append(sops_path)

            # pipeline writes out/<name>.decision.json where name = email basename
            name = os.path.basename(email_path).removesuffix(".json")
            proc = subprocess.run(args, capture_output=True, text=True, timeout=240)
            dec_path = os.path.join(ROOT, "out", "%s.decision.json" % name)
            decision = None
            if os.path.exists(dec_path):
                try:
                    decision = json.load(open(dec_path))
                except Exception:
                    decision = None
            if decision is None:
                # B6: never return stdout/stderr/pipeline logs to the caller;
                # log server-side only.
                print("[bridge] triage failed for %s; stderr tail: %s"
                      % (name, proc.stderr[-500:]))
                return self._send(502, {"error": "triage failed"})
            # B6: return only the routing decision n8n needs — no pipeline_log.
            self._send(200, {"decision": decision})
        finally:
            for p in tmp_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    print("[bridge] listening on http://%s:%d  (POST /triage, GET /health)" % (HOST, PORT))
    Server((HOST, PORT), Handler).serve_forever()
