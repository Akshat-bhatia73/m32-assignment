"""Organization / team management — view the workspace, rename it, invite teammates by email
(sent via the existing Composio Gmail path), revoke invites, and remove members."""

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.agents.tools import composio_tools
from app.api.deps import CurrentMembership, CurrentUser, DbSession
from app.config import settings
from app.models import Invitation, Membership, Organization
from app.schemas.org import InvitationOut, InviteCreate, OrgOut, OrgUpdate
from app.services import orgs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/org", tags=["org"])


def _require_owner(membership: Membership) -> None:
    if membership.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can do that.")


def _pending_invites(db: DbSession, org_id: uuid.UUID) -> list[Invitation]:
    return list(
        db.scalars(
            select(Invitation)
            .where(Invitation.org_id == org_id, Invitation.status == "pending")
            .order_by(Invitation.created_at.desc())
        )
    )


def _org_out(db: DbSession, org: Organization, membership: Membership) -> OrgOut:
    return OrgOut(
        id=org.id,
        name=org.name,
        role=membership.role,
        member_cap=settings.org_member_cap,
        members=orgs.org_roster(db, org.id),
        invites=[InvitationOut.model_validate(i) for i in _pending_invites(db, org.id)],
    )


def _get_org(db: DbSession, membership: Membership) -> Organization:
    org = db.get(Organization, membership.org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    return org


@router.get("", response_model=OrgOut)
def get_org(membership: CurrentMembership, db: DbSession) -> OrgOut:
    return _org_out(db, _get_org(db, membership), membership)


@router.patch("", response_model=OrgOut)
def rename_org(payload: OrgUpdate, membership: CurrentMembership, db: DbSession) -> OrgOut:
    _require_owner(membership)
    org = _get_org(db, membership)
    org.name = payload.name.strip()[:200]
    db.commit()
    db.refresh(org)
    return _org_out(db, org, membership)


def _send_invite_email(
    *, inviter_email: str, invitee: str, org_name: str, inviter_name: str | None
) -> None:
    """Send the invite via Composio Gmail. Raises on failure so the caller can surface it."""
    signup_url = settings.cors_origins[0] if settings.cors_origins else ""
    who = inviter_name or inviter_email
    body = (
        f"Hi,\n\n{who} invited you to join the “{org_name}” workspace on Meeting → Done, "
        "an ops copilot that turns meeting notes into tracked action items and follow-ups.\n\n"
        f"To join, sign up with this email address ({invitee}) here:\n{signup_url}\n\n"
        "You'll land straight in the shared workspace.\n\nSee you there!"
    )
    result = composio_tools.send_gmail(
        user_id=inviter_email,
        to=[invitee],
        subject=f"{who} invited you to {org_name}",
        body=body,
    )
    if result.get("status") == "error":
        raise RuntimeError(result.get("error") or "Gmail send failed")


@router.post("/invites", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreate, current_user: CurrentUser, membership: CurrentMembership, db: DbSession
) -> OrgOut:
    _require_owner(membership)
    org = _get_org(db, membership)
    email = payload.email.lower()

    # Cap counts current members + outstanding invites against the limit.
    if orgs.member_count(db, org.id) + len(_pending_invites(db, org.id)) >= settings.org_member_cap:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This workspace is at its {settings.org_member_cap}-member limit.",
        )

    existing = db.scalar(
        select(Invitation).where(
            Invitation.org_id == org.id,
            func.lower(Invitation.email) == email,
            Invitation.status == "pending",
        )
    )
    invite = existing or Invitation(
        org_id=org.id,
        email=email,
        name=payload.name,
        token=orgs.new_invite_token(),
        role="member",
        status="pending",
        invited_by=current_user.id,
    )
    if existing is None:
        db.add(invite)
        db.commit()

    # Dogfood the integration: send the invite via Gmail.
    try:
        _send_invite_email(
            inviter_email=current_user.email,
            invitee=email,
            org_name=org.name,
            inviter_name=current_user.name,
        )
    except Exception as exc:  # noqa: BLE001 — keep the invite, but tell the owner sending failed
        logger.error("Invite email to %s failed: %s", email, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Invite created, but I couldn't email it (check Gmail in Settings): {exc}",
        ) from exc

    return _org_out(db, org, membership)


@router.delete("/invites/{invite_id}", response_model=OrgOut)
def revoke_invite(
    invite_id: uuid.UUID, membership: CurrentMembership, db: DbSession
) -> OrgOut:
    _require_owner(membership)
    invite = db.get(Invitation, invite_id)
    if invite is None or invite.org_id != membership.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    invite.status = "revoked"
    db.commit()
    return _org_out(db, _get_org(db, membership), membership)


@router.delete("/members/{member_id}", response_model=OrgOut)
def remove_member(
    member_id: uuid.UUID, membership: CurrentMembership, db: DbSession
) -> OrgOut:
    _require_owner(membership)
    target = db.get(Membership, member_id)
    if target is None or target.org_id != membership.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if target.role == "owner":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't remove the workspace owner.")
    db.delete(target)
    db.commit()
    return _org_out(db, _get_org(db, membership), membership)
