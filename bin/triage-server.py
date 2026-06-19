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
import json, os, subprocess, time, http.server, socketserver

ROOT = os.path.expanduser("~/Arvin")
HOST, PORT = "127.0.0.1", 8088

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
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
            payload = json.loads(raw) if raw.strip() else {}
        except Exception as e:
            return self._send(400, {"error": "bad json", "detail": str(e)})

        # Accept two shapes:
        #   { email: {...}, sops: [...] }   <-- new (Drive-fed)
        #   { from, subject, body, ... }    <-- legacy (disk-fed)
        sops = None
        if isinstance(payload, dict) and "email" in payload and "sops" in payload:
            email = payload.get("email") or {}
            sops = payload.get("sops") or []
        else:
            email = payload

        name = "req-%d" % int(time.time() * 1000)
        email_path = "/tmp/%s.json" % name
        with open(email_path, "w") as f:
            json.dump(email, f)

        args = ["bash", os.path.join(ROOT, "bin", "triage-pipeline.sh"), email_path]
        if sops is not None:
            sops_path = "/tmp/%s.sops.json" % name
            with open(sops_path, "w") as f:
                json.dump(sops, f)
            args.append(sops_path)

        proc = subprocess.run(args, capture_output=True, text=True, timeout=240)
        dec_path = os.path.join(ROOT, "out", "%s.decision.json" % name)
        decision = None
        if os.path.exists(dec_path):
            try:
                decision = json.load(open(dec_path))
            except Exception:
                decision = None
        if decision is None:
            return self._send(502, {"error": "triage failed",
                                    "stdout": proc.stdout[-4000:],
                                    "stderr": proc.stderr[-2000:]})
        self._send(200, {"decision": decision, "pipeline_log": proc.stdout[-4000:]})

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    print("[bridge] listening on http://%s:%d  (POST /triage, GET /health)" % (HOST, PORT))
    Server((HOST, PORT), Handler).serve_forever()
