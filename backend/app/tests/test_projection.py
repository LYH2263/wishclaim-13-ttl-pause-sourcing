from datetime import datetime, timedelta, timezone
from app.engines.projection import remaining_seconds, wish_projection

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_claimed_remaining_ticks_with_now():
    exp = (NOW + timedelta(minutes=30)).isoformat()
    assert remaining_seconds("claimed", exp, None, NOW) == 1800
    later = NOW + timedelta(minutes=10)
    assert remaining_seconds("claimed", exp, None, later) == 1200


def test_paused_remaining_is_frozen():
    exp = (NOW + timedelta(hours=1)).isoformat()
    paused_at = (NOW + timedelta(minutes=20)).isoformat()
    # 冻结值 = expires_at - paused_at = 40min, 不随 now 流逝
    assert remaining_seconds("sourcing_paused", exp, paused_at, NOW) == 2400
    assert remaining_seconds("sourcing_paused", exp, paused_at, NOW + timedelta(days=7)) == 2400


def test_remaining_none_for_inactive_status():
    assert remaining_seconds("open", None, None, NOW) is None
    assert remaining_seconds("fulfilled", None, None, NOW) is None


def test_projection_labels_paused():
    row = {"status": "sourcing_paused",
           "expires_at": (NOW + timedelta(hours=1)).isoformat(),
           "paused_at": (NOW + timedelta(minutes=20)).isoformat()}
    p = wish_projection(row, NOW + timedelta(days=1))
    assert p["paused"] is True
    assert p["remaining_seconds"] == 2400
    assert p["countdown"] == "已暂停 · 剩余 2400s"


def test_projection_labels_claimed():
    row = {"status": "claimed", "expires_at": (NOW + timedelta(seconds=90)).isoformat(),
           "paused_at": None}
    p = wish_projection(row, NOW)
    assert p["paused"] is False
    assert p["remaining_seconds"] == 90
    assert p["countdown"] == "剩余 90s"
