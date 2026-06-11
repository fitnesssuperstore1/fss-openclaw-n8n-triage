#!/usr/bin/env python3
"""Create a Gmail DRAFT (never sends) by IMAP-appending to [Gmail]/Drafts.

Phase-1 safety: this tool can ONLY append to the Drafts folder. There is no
SMTP/send path anywhere in this project, so 'no auto-send' is structural.

Usage: make-draft.py <decision.json>
Reads draft.{to,subject,body} from the decision. If draft is null
(escalation-only), it does nothing and exits 0.

Env / secrets:
  GMAIL_USER            (default: mike@brownmine.com)
  ~/secrets/gmail_app.key   Gmail app password (16 chars, no spaces)
"""
import json, os, sys, ssl, time, imaplib
from email.message import EmailMessage

GMAIL_USER = os.environ.get("GMAIL_USER", "mike@brownmine.com")
APP_PW_FILE = os.path.expanduser("~/secrets/gmail_app.key")
DRAFTS_FOLDER = '"[Gmail]/Drafts"'

def main():
    if len(sys.argv) < 2:
        print("usage: make-draft.py <decision.json>", file=sys.stderr); sys.exit(2)
    dec = json.load(open(sys.argv[1], encoding="utf-8"))
    draft = dec.get("draft")
    if not draft:
        print("[make-draft] action=%s, no draft to create (escalation-only)."
              % dec.get("action"))
        return
    if not os.path.exists(APP_PW_FILE) or os.path.getsize(APP_PW_FILE) == 0:
        print("missing %s" % APP_PW_FILE, file=sys.stderr); sys.exit(1)
    app_pw = open(APP_PW_FILE).read().strip()

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = draft.get("to", "")
    msg["Subject"] = draft.get("subject", "(no subject)")
    msg.set_content(draft.get("body", ""))

    ctx = ssl.create_default_context()
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
    try:
        M.login(GMAIL_USER, app_pw)
        typ, data = M.append(DRAFTS_FOLDER, r'(\Draft)',
                             imaplib.Time2Internaldate(time.time()),
                             msg.as_bytes())
        print("[make-draft] append -> %s %s | to=%s | subject=%s"
              % (typ, (data[0].decode() if data and data[0] else ""),
                 msg["To"], msg["Subject"]))
    finally:
        try: M.logout()
        except Exception: pass

if __name__ == "__main__":
    main()
