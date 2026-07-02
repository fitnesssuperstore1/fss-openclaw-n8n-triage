## docker compose config: VALID  |  docker compose build: both images Built

## service health (docker compose ps)
bridge  Up 43 minutes
n8n  Up 43 minutes
openclaw  Up 31 minutes

## ports — bound to 127.0.0.1 only (not publicly reachable)
  LISTEN 127.0.0.1:18790
  LISTEN 127.0.0.1:8088
  LISTEN 127.0.0.1:8080
  LISTEN [::1]:18790

## bridge health
  GET /health -> 200

## n8n-import (clean-clone workflow seed)
  n8n-import-1  | Successfully imported 2 workflows.

