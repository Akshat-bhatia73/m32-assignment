"""Resolve free-text action-item owners to real workspace members.

The LLM extracts an owner as plain text (a first name, a full name, or an email). When the
workspace has teammates, we match that text to a member so items get *assigned* to a real person
(canonical name on the board, real email on follow-ups) instead of dangling as a loose string.
"""

from typing import Any


def _member_index(
    members: list[dict[str, Any]],
) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """Build lookup maps (by email / full name / first name) → (display_name, email)."""
    by_email: dict[str, tuple[str, str]] = {}
    by_name: dict[str, tuple[str, str]] = {}
    by_first: dict[str, tuple[str, str]] = {}
    for m in members:
        email = (m.get("email") or "").strip()
        name = (m.get("name") or "").strip()
        display = name or email
        if email:
            by_email[email.lower()] = (display, email)
            by_first.setdefault(email.split("@")[0].lower(), (display, email))
        if name:
            by_name[name.lower()] = (display, email)
            by_first.setdefault(name.split()[0].lower(), (display, email))
    return by_email, by_name, by_first


def resolve_member(
    owner: str | None, members: list[dict[str, Any]]
) -> tuple[str, str] | None:
    """Return (display_name, email) for an owner matched to a member, or None if no match."""
    if not owner:
        return None
    key = owner.strip().lower()
    if not key:
        return None
    by_email, by_name, by_first = _member_index(members)
    return by_email.get(key) or by_name.get(key) or by_first.get(key.split()[0])


def resolve_owner_name(owner: str | None, members: list[dict[str, Any]]) -> str | None:
    """Canonicalize an owner to the matched member's display name; pass through if no match."""
    hit = resolve_member(owner, members)
    return hit[0] if hit else owner


def resolve_owner_emails(
    items: list[dict[str, Any]], members: list[dict[str, Any]]
) -> set[str]:
    """Collect the real emails of teammates who own any of these items."""
    emails: set[str] = set()
    for item in items:
        hit = resolve_member(item.get("owner"), members)
        if hit and hit[1]:
            emails.add(hit[1])
    return emails
