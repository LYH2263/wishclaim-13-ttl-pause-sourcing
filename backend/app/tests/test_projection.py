from datetime import datetime, timedelta, timezone
from app.engines.claim_lock import parse_ts
from app.engines.sourcing_pause import PAUSED, resume_payload
from app.projections.wish import project_wish

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _row(status="claimed", claimer="alice", paused_at=None, expires_at=None):
    return {"status": status, "claimer": claimer, "paused_at": paused_at,
            "expires_at": expires_at}


def test_claimed_live_remaining():
    row = _row(expires_at=(NOW + timedelta(seconds=120)).isoformat())
    p = project_wish(row, NOW)
    assert p["is_paused"] is False and p["remaining_seconds"] == 120


def test_claimed_remaining_clamped_at_zero():
    row = _row(expires_at=(NOW - timedelta(seconds=5)).isoformat())
    assert project_wish(row, NOW)["remaining_seconds"] == 0


def test_paused_remaining_is_frozen():
    paused_at = (NOW - timedelta(minutes=10)).isoformat()
    expires_at = (NOW + timedelta(minutes=50)).isoformat()
    row = _row(status=PAUSED, paused_at=paused_at, expires_at=expires_at)
    p = project_wish(row, NOW)
    assert p["is_paused"] is True and p["remaining_seconds"] == 3600
    # Independent of wall clock: a week later the frozen value is unchanged.
    assert project_wish(row, NOW + timedelta(days=7))["remaining_seconds"] == 3600


def test_other_states_have_no_remaining():
    for s in ("open", "released"):
        p = project_wish(_row(status=s, claimer=None, expires_at=None), NOW)
        assert p["remaining_seconds"] is None and p["is_paused"] is False
    # fulfilled rows may carry a stale expires_at; it must not project a countdown.
    p = project_wish(_row(status="fulfilled", expires_at=(NOW + timedelta(hours=1)).isoformat()), NOW)
    assert p["remaining_seconds"] is None and p["is_paused"] is False


def test_paused_missing_timestamp():
    p = project_wish(_row(status=PAUSED, paused_at=None, expires_at=None), NOW)
    assert p["is_paused"] is True and p["remaining_seconds"] is None


def test_projection_matches_resume_formula():
    paused_at = (NOW - timedelta(minutes=10)).isoformat()
    expires_at = (NOW + timedelta(minutes=50)).isoformat()
    row = _row(status=PAUSED, paused_at=paused_at, expires_at=expires_at)
    projected = project_wish(row, NOW)
    resumed = resume_payload(NOW, paused_at, expires_at)
    assert parse_ts(resumed["expires_at"]) == NOW + timedelta(seconds=projected["remaining_seconds"])
