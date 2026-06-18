"""Unit tests for pure agent helpers (no DB / no network)."""

from app.agents.nodes.comms import (
    _conflict_for,
    _existing_intervals,
    _resolve_owner_emails,
)

MEMBERS = [
    {"id": "1", "name": "Priya Sharma", "email": "priya@acme.com", "role": "owner"},
    {"id": "2", "name": "David Lee", "email": "david@acme.com", "role": "member"},
]


def test_resolve_owner_emails_matches_name_email_and_firstname():
    items = [
        {"owner": "Priya", "task": "a"},  # first name
        {"owner": "david@acme.com", "task": "b"},  # exact email
        {"owner": "Someone Else", "task": "c"},  # unmatched -> skipped
        {"owner": None, "task": "d"},  # no owner -> skipped
    ]
    assert _resolve_owner_emails(items, MEMBERS) == {"priya@acme.com", "david@acme.com"}


def test_resolve_owner_emails_empty_without_members():
    assert _resolve_owner_emails([{"owner": "Priya", "task": "a"}], []) == set()


def test_conflict_detection_timed_and_all_day():
    existing = [
        {
            "summary": "Standup",
            "start": "2026-06-20T09:15:00+00:00",
            "end": "2026-06-20T09:45:00+00:00",
            "all_day": False,
        },
        {"summary": "Holiday", "start": "2026-06-21", "end": "2026-06-22", "all_day": True},
    ]
    intervals = _existing_intervals(existing)
    # Proposed 9:00–9:30 collides with the 9:15 standup.
    assert _conflict_for("2026-06-20", intervals) == "Standup"
    # All-day event makes the whole day busy.
    assert _conflict_for("2026-06-21", intervals) == "Holiday"
    # A free day has no conflict.
    assert _conflict_for("2026-06-23", intervals) is None
