import uuid
from typing import Any

from sqlmodel import Session

from app.models import PdEcrActivity


def write_activity(
    *,
    session: Session,
    action: str,
    case_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    target_type: str = "case",
    target_id: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PdEcrActivity:
    activity = PdEcrActivity(
        action=action,
        case_id=case_id,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        message=message,
        metadata_json=metadata or {},
    )
    session.add(activity)
    return activity
