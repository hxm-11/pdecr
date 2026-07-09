"""PD-ECR attachment persistence.

Stores real uploaded file bytes on disk (``UPLOAD_DIR/pd_ecr``) and one
``PdEcrAttachment`` row per file, classified by ``section`` (before_change,
after_change, feasibility, execution, result, other) and optionally scoped to
a ``module_id``. Replaces the previous frontend-localStorage-only metadata.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import settings
from app.models import PdEcrAttachment, PdEcrCase, User

ALLOWED_SECTIONS = {
    "before_change",
    "after_change",
    "feasibility",
    "execution",
    "result",
    "other",
}


def _attachment_dir() -> Path:
    path = Path(settings.UPLOAD_DIR) / "pd_ecr"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _actor_name(user: User | None) -> str | None:
    if user is None:
        return None
    return getattr(user, "full_name", None) or getattr(user, "email", None)


def normalize_section(section: str | None) -> str:
    value = (section or "other").strip().lower()
    return value if value in ALLOWED_SECTIONS else "other"


def serialize_attachment(attachment: PdEcrAttachment) -> dict[str, Any]:
    return {
        "id": str(attachment.id),
        "case_id": str(attachment.case_id),
        "module_id": attachment.module_id,
        "section": attachment.section,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "file_size": attachment.size_bytes,
        "uploaded_by": str(attachment.uploaded_by_id)
        if attachment.uploaded_by_id
        else None,
        "uploaded_by_name": attachment.uploaded_by_name,
        "created_at": attachment.created_at.isoformat()
        if attachment.created_at
        else None,
    }


def save_attachment(
    *,
    session: Session,
    case: PdEcrCase,
    filename: str,
    content: bytes,
    content_type: str | None,
    section: str | None,
    module_id: str | None,
    current_user: User | None,
    commit: bool = True,
) -> PdEcrAttachment:
    """Persist uploaded bytes to disk and create an attachment row."""
    safe_name = f"{uuid.uuid4().hex}_{filename or 'file'}"
    file_path = _attachment_dir() / safe_name
    try:
        file_path.write_bytes(content)
    except Exception as exc:  # pragma: no cover - disk failure
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    attachment = PdEcrAttachment(
        case_id=case.id,
        filename=filename or "file",
        stored_path=str(file_path),
        content_type=content_type,
        size_bytes=len(content),
        target_type="module" if module_id else "case",
        target_id=module_id,
        section=normalize_section(section),
        module_id=module_id,
        uploaded_by_id=current_user.id if current_user else None,
        uploaded_by_name=_actor_name(current_user),
    )
    session.add(attachment)
    if commit:
        session.commit()
        session.refresh(attachment)
    return attachment


def list_attachments(
    *,
    session: Session,
    case: PdEcrCase,
    section: str | None = None,
    module_id: str | None = None,
) -> list[PdEcrAttachment]:
    statement = select(PdEcrAttachment).where(PdEcrAttachment.case_id == case.id)
    if section:
        statement = statement.where(PdEcrAttachment.section == normalize_section(section))
    if module_id:
        statement = statement.where(PdEcrAttachment.module_id == module_id)
    statement = statement.order_by(PdEcrAttachment.created_at.asc())
    return list(session.exec(statement).all())


def get_attachment_or_404(
    *, session: Session, attachment_id: str
) -> PdEcrAttachment:
    try:
        parsed = uuid.UUID(str(attachment_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Attachment not found")
    attachment = session.get(PdEcrAttachment, parsed)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


def delete_attachment(*, session: Session, attachment: PdEcrAttachment) -> None:
    """Delete the DB row and best-effort remove the stored file."""
    stored = attachment.stored_path
    session.delete(attachment)
    session.commit()
    if stored:
        try:
            Path(stored).unlink(missing_ok=True)
        except OSError:
            # File cleanup is best-effort; the row is already gone.
            pass
