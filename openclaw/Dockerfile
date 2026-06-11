# OpenClaw image — used by BOTH compose services:
#   - openclaw (gateway): entrypoint.sh
#   - bridge (triage HTTP server): bridge-entrypoint.sh
#
# The bridge needs the openclaw CLI (triage-chain.py shells out to
# `openclaw agent --local` per skill call), plus python3 + jsonschema for the
# chain itself and jq for monday-card.sh. Building one image for both keeps
# the CLI versions identical.
#
# Skills are NOT baked in — the host's ./skills folder is bind-mounted into
# the workspace (see docker-compose.yml). Editing a SKILL.md on the host is
# live in the container immediately.
FROM node:22-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-jsonschema jq ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g openclaw && npm cache clean --force

RUN mkdir -p /root/.openclaw/workspace/skills /root/Arvin/out

COPY entrypoint.sh /entrypoint.sh
COPY bridge-entrypoint.sh /bridge-entrypoint.sh
RUN chmod +x /entrypoint.sh /bridge-entrypoint.sh

EXPOSE 18789 8088
ENTRYPOINT ["/entrypoint.sh"]
