"""Organization/membership helpers — auto-create an org on signup, accept invites, build the
member roster the agent uses to resolve action-item owners to real teammate emails.
"""

import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invitation, Membership, Organization, User


def _default_org_name(user: User) -> str:
    base = (user.name or "").strip() or user.email.split("@")[0]
    return f"{base}'s workspace"


def get_user_membership(db: Session, user: User) -> Membership | None:
    """The user's single membership (one org per user), if any."""
    return db.scalar(select(Membership).where(Membership.user_id == user.id))


def member_count(db: Session, org_id) -> int:
    return db.scalar(
        select(func.count()).select_from(Membership).where(Membership.org_id == org_id)
    ) or 0


def accept_invitation(db: Session, invite: Invitation, user: User) -> Membership:
    """Attach the user to the invite's org as a member and mark the invite accepted."""
    membership = Membership(org_id=invite.org_id, user_id=user.id, role=invite.role or "member")
    db.add(membership)
    invite.status = "accepted"
    invite.accepted_at = datetime.now(UTC)
    return membership


def ensure_membership(db: Session, user: User) -> Membership:
    """Guarantee the user belongs to an org. Called on signup/login.

    If a pending invite matches their email, they join that org (member). Otherwise we create
    their own workspace with them as owner. Commits before returning.
    """
    existing = get_user_membership(db, user)
    if existing is not None:
        return existing

    invite = db.scalar(
        select(Invitation)
        .where(
            func.lower(Invitation.email) == user.email.lower(),
            Invitation.status == "pending",
        )
        .order_by(Invitation.created_at.desc())
    )
    if invite is not None and member_count(db, invite.org_id) < _cap():
        membership = accept_invitation(db, invite, user)
        db.commit()
        db.refresh(membership)
        return membership

    org = Organization(name=_default_org_name(user), owner_user_id=user.id)
    db.add(org)
    db.flush()  # assign org.id
    membership = Membership(org_id=org.id, user_id=user.id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def org_roster(db: Session, org_id) -> list[dict]:
    """[{id, name, email, role}] for every member of the org (for UI + owner resolution)."""
    rows = db.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.org_id == org_id)
        .order_by(Membership.created_at)
    ).all()
    return [
        {"id": str(u.id), "name": u.name, "email": u.email, "role": role} for u, role in rows
    ]


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


def _cap() -> int:
    from app.config import settings

    return settings.org_member_cap
