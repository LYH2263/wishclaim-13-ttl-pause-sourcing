"""Sourcing pause state machine for claimed wishes.

A claimer may freeze the claim TTL while sourcing the gift:
claimed -> sourcing_paused -> claimed. While paused the TTL sweep
never releases the wish, and the remaining lock time is frozen:
on resume the deadline becomes `now + (expires_at - paused_at)`.
Pure functions only, mirroring engines/claim_lock.py conventions.

Transfer is intentionally not implemented yet; the "no transfer while
paused" rule is reserved here (owned vs. releasable states are kept
separate) and pinned in the /api/rules copy.
"""
from datetime import datetime, timedelta
from app.engines.claim_lock import parse_ts

PAUSED = "sourcing_paused"
_OWNED_STATES = frozenset(("claimed", PAUSED))
RELEASEABLE_STATES = frozenset(("claimed", PAUSED))


def pause_allowed(status: str, claimer: str | None, actor: str) -> dict:
    """Only the current claimer can pause, and only a live claimed wish."""
    if status in _OWNED_STATES and claimer != actor:
        return {"ok": False, "reason": "not_claimer"}
    if status == PAUSED:
        return {"ok": False, "reason": "already_paused"}
    if status in _OWNED_STATES:
        return {"ok": True, "reason": ""}
    if status == "fulfilled":
        return {"ok": False, "reason": "already_fulfilled"}
    return {"ok": False, "reason": "not_claimed"}


def pause_payload(now: datetime) -> dict:
    return {"status": PAUSED, "paused_at": now.isoformat()}


def frozen_remaining_delta(paused_at: str, expires_at: str) -> timedelta:
    """Remaining TTL frozen at pause time. Single source of truth shared by
    resume_payload and the projection; clamped at zero."""
    d = parse_ts(expires_at) - parse_ts(paused_at)
    return d if d > timedelta(0) else timedelta(0)


def resume_allowed(status: str, claimer: str | None, actor: str,
                   paused_at: str | None, expires_at: str | None) -> dict:
    if status != PAUSED:
        return {"ok": False, "reason": "not_paused"}
    if claimer != actor:
        return {"ok": False, "reason": "not_claimer"}
    if not paused_at:
        return {"ok": False, "reason": "missing_paused_at"}
    if not expires_at:
        return {"ok": False, "reason": "missing_expires_at"}
    return {"ok": True, "reason": ""}


def resume_payload(now: datetime, paused_at: str, expires_at: str) -> dict:
    exp = now + frozen_remaining_delta(paused_at, expires_at)
    return {"status": "claimed", "paused_at": None, "expires_at": exp.isoformat()}


def fulfill_allowed(status: str) -> dict:
    """Fulfill is forbidden while sourcing is paused; otherwise only claimed
    wishes can be fulfilled (preserves the historical need_claim reason)."""
    if status == "claimed":
        return {"ok": True, "reason": ""}
    if status == PAUSED:
        return {"ok": False, "reason": PAUSED}
    return {"ok": False, "reason": "need_claim"}


def release_allowed(status: str) -> bool:
    """Release works from claimed and paused (the no-auth escape hatch that
    also un-sticks permanently-exempt paused rows)."""
    return status in RELEASEABLE_STATES
