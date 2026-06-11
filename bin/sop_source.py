"""SOP source abstraction.

The triage chain consumes SOPs through this layer so the underlying source can
change without touching chain code or skill prompts.

Current Phase 1 wiring:
    n8n's Drive Search + Download nodes fetch the SOP catalog -> the bridge
    serialises the list and passes it to triage-chain.py as a JSON file ->
    the chain wraps it in `InMemorySopSource` -> select_sop and draft_response
    consume the catalog through `list_sops()` / `get_sop()`.

Planned Milestone 2 wiring:
    The chain instantiates `IndexSopSource` (or whatever production search
    system the client provides) -> the chain calls list_sops / get_sop the
    same way -> no change to triage-chain.py main flow or the skills.

The abstraction is intentionally tiny: two methods. Anything more (per-lane
ranking, semantic search, etc.) belongs inside the concrete implementation.
"""
from __future__ import annotations
import json
import pathlib
from typing import List, Optional


class Sop(dict):
    """Thin dict subclass so SOP objects can still be json.dumps'd as-is when
    handed to OpenClaw skill prompts, while also exposing readable properties
    for in-code access.

    Expected shape per SOP:
        id      (str)   e.g. "SOP-04", "REF-01", "ARCH-01"
        name    (str)   filename (when known)
        title   (str)   human title (when known)
        status  (str)   "Active" | "Reference" | "Archived"
        lane    (str)   workflow lane (optional — not all SOPs are lane-bound)
        content (str)   full markdown body (optional for catalog-only views)
        summary (str)   one-line trigger summary (optional, used by select_sop)
    """

    @property
    def id(self) -> Optional[str]:
        return self.get("id")

    @property
    def status(self) -> Optional[str]:
        return self.get("status")

    @property
    def lane(self) -> Optional[str]:
        return self.get("lane")

    @property
    def title(self) -> str:
        return self.get("title") or self.get("name", "")

    @property
    def content(self) -> str:
        return self.get("content", "")


class SopSource:
    """Abstract base. Implementations MUST provide list_sops and get_sop."""

    def list_sops(self, lane: Optional[str] = None) -> List[Sop]:
        raise NotImplementedError

    def get_sop(self, sop_id: str) -> Optional[Sop]:
        raise NotImplementedError


class InMemorySopSource(SopSource):
    """Wraps a list of SOP dicts that were fetched upstream (currently by n8n's
    Drive Search + Download nodes). This is the Phase 1 / Milestone 1 default.

    If `lane` is passed to list_sops, only SOPs whose own `lane` attribute
    matches are returned. Passing None returns the entire catalog (which is the
    common case — select_sop is fed the full catalog so it can detect cross-lane
    archived conflicts)."""

    def __init__(self, sops: Optional[List[dict]] = None):
        self._sops: List[Sop] = [Sop(s) for s in (sops or [])]

    def list_sops(self, lane: Optional[str] = None) -> List[Sop]:
        if lane is None:
            return list(self._sops)
        return [s for s in self._sops if (s.lane or "") == lane]

    def get_sop(self, sop_id: str) -> Optional[Sop]:
        if not sop_id:
            return None
        return next((s for s in self._sops if s.id == sop_id), None)

    @classmethod
    def from_json_file(cls, path: Optional[str]) -> "InMemorySopSource":
        """Construct from a sops.json file on disk (the bridge writes one of
        these per request from the n8n payload). Empty source if path is
        falsy or the file is missing/empty."""
        if not path:
            return cls([])
        p = pathlib.Path(path)
        if not p.exists() or not p.read_text().strip():
            return cls([])
        return cls(json.loads(p.read_text()))


class IndexSopSource(SopSource):
    """Placeholder for the production SOP Index / RAG system the client plans
    to wire up in Milestone 2. The exact interface is TBD — whoever implements
    it should:

      1. Replace the body of list_sops and get_sop with real index calls.
      2. Keep the return shape the same (a list of Sop dicts / a single Sop).
      3. Leave the chain and skill prompts untouched.

    Calling either method on the stub raises so misconfiguration is obvious."""

    def __init__(self, **config):
        self._config = config

    def list_sops(self, lane: Optional[str] = None) -> List[Sop]:
        raise NotImplementedError(
            "IndexSopSource is a Milestone 2 stub. Wire it to the production "
            "SOP index before instantiating it in triage-chain.py."
        )

    def get_sop(self, sop_id: str) -> Optional[Sop]:
        raise NotImplementedError(
            "IndexSopSource is a Milestone 2 stub. Wire it to the production "
            "SOP index before instantiating it in triage-chain.py."
        )
