"""Read-model projection for wish rows.

Adds derived countdown fields to the raw SQLite row so every read endpoint
speaks one TTL dialect:
  is_paused         — status == sourcing_paused
  remaining_seconds — claimed: live seconds until expires_at (clamped at 0)
                      sourcing_paused: frozen seconds from pause time (independent of now)
                      everything else: None (incl. fulfilled rows carrying a stale expires_at)
"""
from datetime import datetime
from typing import Iterable, Mapping
from app.engines.claim_lock import parse_ts
from app.engines.sourcing_pause import PAUSED, frozen_remaining_delta


def project_wish(row: Mapping, now: datetime) -> dict:
    d = dict(row)
    status = d.get("status")
    d["is_paused"] = status == PAUSED
    remaining = None
    expires_at = d.get("expires_at")
    if status == "claimed" and expires_at:
        remaining = int(round(max(0, (parse_ts(expires_at) - now).total_seconds())))
    elif status == PAUSED and expires_at and d.get("paused_at"):
        remaining = int(round(
            frozen_remaining_delta(d["paused_at"], expires_at).total_seconds()))
    d["remaining_seconds"] = remaining
    return d


def project_wishes(rows: Iterable[Mapping], now: datetime) -> list:
    return [project_wish(r, now) for r in rows]
