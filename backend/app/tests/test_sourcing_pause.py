from datetime import datetime, timedelta, timezone
from app.engines.claim_lock import claim_allowed, release_if_expired
from app.engines.sourcing_pause import (
    PAUSED, action_allowed, pause_allowed, pause_payload, resume_allowed, resume_payload,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_pause_only_by_current_claimer():
    assert pause_allowed("claimed", "alice", "alice")["ok"] is True
    r = pause_allowed("claimed", "alice", "bob")
    assert r["ok"] is False and r["reason"] == "not_claimer"


def test_pause_requires_claimed_status():
    for st in ("open", "released", "fulfilled", PAUSED):
        r = pause_allowed(st, "alice", "alice")
        assert r["ok"] is False and r["reason"] == "not_claimed"


def test_pause_payload_freezes_clock():
    p = pause_payload(NOW)
    assert p["status"] == PAUSED and p["paused_at"] == NOW.isoformat()


def test_resume_only_by_current_claimer():
    assert resume_allowed(PAUSED, "alice", "alice")["ok"] is True
    r = resume_allowed(PAUSED, "alice", "bob")
    assert r["ok"] is False and r["reason"] == "not_claimer"
    r = resume_allowed("claimed", "alice", "alice")
    assert r["ok"] is False and r["reason"] == "not_paused"


def test_resume_recomputes_expires_at_frozen_remaining():
    # 认领时 expires_at = 13:00, 12:20 暂停 -> 冻结剩余 40min
    expires_at = (NOW + timedelta(hours=1)).isoformat()
    paused_at = (NOW + timedelta(minutes=20)).isoformat()
    # 暂停 3 小时后恢复: expires_at = 恢复时刻 + 40min (剩余秒冻结续跑)
    resume_now = NOW + timedelta(hours=3)
    p = resume_payload(expires_at, paused_at, resume_now)
    assert p["status"] == "claimed" and p["paused_at"] is None
    assert p["expires_at"] == (resume_now + timedelta(minutes=40)).isoformat()


def test_resume_clamps_negative_remaining():
    expires_at = NOW.isoformat()
    paused_at = (NOW + timedelta(minutes=5)).isoformat()
    p = resume_payload(expires_at, paused_at, NOW + timedelta(hours=1))
    assert p["expires_at"] == (NOW + timedelta(hours=1)).isoformat()


def test_paused_blocks_transfer_and_fulfill():
    for action in ("transfer", "claim", "fulfill"):
        r = action_allowed(PAUSED, action)
        assert r["ok"] is False and r["reason"] == "sourcing_paused"
    for action in ("resume", "release"):
        assert action_allowed(PAUSED, action)["ok"] is True
    assert action_allowed("claimed", "fulfill")["ok"] is True


def test_ttl_sweep_never_releases_paused():
    # 暂停期 TTL 扫尾不得释放, 哪怕 expires_at 早已过去
    past = (NOW - timedelta(days=1)).isoformat()
    assert release_if_expired(PAUSED, past, NOW) is None


def test_claim_rejected_while_paused():
    r = claim_allowed(PAUSED, "alice", NOW, (NOW + timedelta(hours=1)).isoformat())
    assert r["ok"] is False and r["reason"] == "sourcing_paused"
