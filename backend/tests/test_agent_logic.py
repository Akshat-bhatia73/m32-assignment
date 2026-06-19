"""Unit tests for pure agent helpers (no DB / no network)."""

from app.agents.nodes.comms import (
    _conflict_for,
    _existing_intervals,
    _resolve_owner_emails,
)
from app.services.transcript import _clean_captions

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


def test_clean_captions_srt_strips_indices_and_timestamps():
    srt = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Welcome to the sync.\n\n"
        "2\n"
        "00:00:04,500 --> 00:00:07,000\n"
        "Priya fixes the login bug by Friday.\n"
    )
    assert _clean_captions(srt) == "Welcome to the sync.\nPriya fixes the login bug by Friday."


def test_clean_captions_vtt_strips_header_tags_and_dedupes():
    vtt = (
        "WEBVTT\n\n"
        "NOTE recorded by Meet\n\n"
        "00:00:01.000 --> 00:00:04.000\n"
        "<v Priya>Let us start.</v>\n"
        "<v Priya>Let us start.</v>\n\n"
        "00:00:05.000 --> 00:00:08.000\n"
        "David ships the report tomorrow.\n"
    )
    assert _clean_captions(vtt) == "Let us start.\nDavid ships the report tomorrow."
