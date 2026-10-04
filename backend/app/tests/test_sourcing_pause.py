from datetime import datetime, timedelta, timezone
from app.engines.sourcing_pause import (
    PAUSED, RELEASEABLE_STATES,
    pause_allowed, pause_payload, frozen_remaining_delta,
    resume_allowed, resume_payload, fulfill_allowed, release_allowed,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_pause_allowed_owner_and_outsider():
    ok = pause_allowed("claimed", "alice", "alice")
    assert ok["ok"] and ok["reason"] == ""
    bad = pause_allowed("claimed", "alice", "bob")
    assert bad["ok"] is False and bad["reason"] == "not_claimer"
    again = pause_allowed(PAUSED, "alice", "alice")
    assert again["ok"] is False and again["reason"] == "already_paused"


def test_pause_allowed_wrong_states():
    for s in ("open", "released"):
        d = pause_allowed(s, "alice", "alice")
        assert d["ok"] is False and d["reason"] == "not_claimed"
    d = pause_allowed("fulfilled", "alice", "alice")
    assert d["ok"] is False and d["reason"] == "already_fulfilled"


def test_pause_payload():
    p = pause_payload(NOW)
    assert p["status"] == PAUSED and p["paused_at"] == NOW.isoformat()


def test_frozen_remaining_delta_clamps():
    paused_at = (NOW - timedelta(minutes=10)).isoformat()
    expires_at = (NOW + timedelta(minutes=50)).isoformat()
    assert frozen_remaining_delta(paused_at, expires_at) == timedelta(seconds=3600)
    assert frozen_remaining_delta(expires_at, paused_at) == timedelta(0)


def test_resume_allowed_branches():
    paused_at = (NOW - timedelta(minutes=10)).isoformat()
    expires_at = (NOW + timedelta(minutes=50)).isoformat()
    ok = resume_allowed(PAUSED, "alice", "alice", paused_at, expires_at)
    assert ok["ok"]
    assert resume_allowed(PAUSED, "alice", "bob", paused_at, expires_at)["reason"] == "not_claimer"
    assert resume_allowed("claimed", "alice", "alice", paused_at, expires_at)["reason"] == "not_paused"
    assert resume_allowed(PAUSED, "alice", "alice", None, expires_at)["reason"] == "missing_paused_at"
    assert resume_allowed(PAUSED, "alice", "alice", paused_at, None)["reason"] == "missing_expires_at"


def test_resume_payload_recomputes_expiry():
    paused_at = (NOW - timedelta(minutes=10)).isoformat()
    expires_at = (NOW + timedelta(minutes=50)).isoformat()
    p = resume_payload(NOW, paused_at, expires_at)
    assert p["status"] == "claimed" and p["paused_at"] is None
    assert p["expires_at"] == (NOW + timedelta(seconds=3600)).isoformat()


def test_resume_payload_zero_remaining():
    p = resume_payload(NOW, NOW.isoformat(), NOW.isoformat())
    assert p["expires_at"] == NOW.isoformat()


def test_multi_cycle_budget_invariant():
    # Cycle 1: 1h budget; pause 50min in -> 10min frozen; resume 2min later.
    t0 = NOW
    e0 = t0 + timedelta(hours=1)
    p1 = t0 + timedelta(minutes=50)
    r1 = frozen_remaining_delta(p1.isoformat(), e0.isoformat())
    q1 = p1 + timedelta(minutes=2)
    e1 = q1 + r1
    # Cycle 2: 5min of live claim after the resume, then pause 3 days.
    p2 = q1 + timedelta(minutes=5)
    r2 = frozen_remaining_delta(p2.isoformat(), e1.isoformat())
    q2 = p2 + timedelta(days=3)
    e2 = q2 + r2
    # Total live consumed: 50 + 5 = 55min of the 60min budget -> 5min remains.
    assert r1 == timedelta(minutes=10)
    assert r2 == timedelta(minutes=5)
    assert e2 - q2 == timedelta(minutes=5)


def test_fulfill_allowed_branches():
    assert fulfill_allowed("claimed")["ok"]
    d = fulfill_allowed(PAUSED)
    assert d["ok"] is False and d["reason"] == PAUSED
    for s in ("open", "released", "fulfilled"):
        assert fulfill_allowed(s)["reason"] == "need_claim"


def test_release_allowed():
    assert release_allowed("claimed")
    assert release_allowed(PAUSED)
    for s in ("open", "released", "fulfilled"):
        assert release_allowed(s) is False
    assert RELEASEABLE_STATES == frozenset(("claimed", PAUSED))
