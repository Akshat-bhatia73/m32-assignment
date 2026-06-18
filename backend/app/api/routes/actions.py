"""Action Board REST API. The agent's board_tools mutate the same table."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import ActionItem, ChatSession
from app.models.action_item import ACTION_STATUSES
from app.schemas.action import ActionItemOut, ActionItemUpdate, ActionItemWithSession

router = APIRouter(tags=["actions"])


@router.get("/actions", response_model=list[ActionItemWithSession])
def list_all_actions(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: str | None = None,
) -> list[ActionItemWithSession]:
    """Every action item for the current user across all sessions (overview screen)."""
    stmt = (
        select(ActionItem, ChatSession.title)
        .join(ChatSession, ActionItem.session_id == ChatSession.id)
        .where(ActionItem.user_id == current_user.id)
        .order_by(ActionItem.created_at.desc())
    )
    if status_filter and status_filter in ACTION_STATUSES:
        stmt = stmt.where(ActionItem.status == status_filter)
    rows = db.execute(stmt).all()
    return [
        ActionItemWithSession(
            **ActionItemOut.model_validate(item).model_dump(),
            session_title=title or "Untitled",
        )
        for item, title in rows
    ]


@router.get("/sessions/{session_id}/actions", response_model=list[ActionItemOut])
def list_actions(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[ActionItem]:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    rows = db.scalars(
        select(ActionItem)
        .where(ActionItem.session_id == session_id)
        .order_by(ActionItem.created_at)
    ).all()
    return list(rows)


def _owned_action(db: DbSession, action_id: uuid.UUID, user_id: uuid.UUID) -> ActionItem:
    item = db.get(ActionItem, action_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action item not found")
    return item


@router.patch("/actions/{action_id}", response_model=ActionItemOut)
def update_action(
    action_id: uuid.UUID,
    payload: ActionItemUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ActionItem:
    item = _owned_action(db, action_id, current_user.id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in ACTION_STATUSES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid status")
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(action_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    item = _owned_action(db, action_id, current_user.id)
    db.delete(item)
    db.commit()
