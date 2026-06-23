import uuid
from typing import Any, List

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import SessionDep, CurrentUser
from app.models import (
    Project,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=List[ProjectRead])
def read_projects(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    statement = select(Project).where(Project.owner_id == current_user.id).offset(skip).limit(limit)
    projects = session.exec(statement).all()
    return projects


@router.get("/{id}", response_model=ProjectRead)
def read_project(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return project


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    session: SessionDep, current_user: CurrentUser, project_in: ProjectCreate
) -> Any:
    project = Project.from_orm(project_in)
    project.owner_id = current_user.id
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.put("/{id}", response_model=ProjectRead)
def update_project(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID, project_in: ProjectUpdate
) -> Any:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    project_data = project_in.model_dump(exclude_unset=True)
    for key, value in project_data.items():
        setattr(project, key, value)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> None:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(project)
    session.commit()