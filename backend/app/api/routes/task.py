import uuid
from typing import Any, List

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import SessionDep, CurrentUser
from app.models import (
    Task,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=List[TaskRead])
def read_tasks(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    statement = select(Task).offset(skip).limit(limit)
    tasks = session.exec(statement).all()
    # 可根据业务需求过滤当前用户相关任务
    return tasks


@router.get("/{id}", response_model=TaskRead)
def read_task(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    task = session.get(Task, id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    # 可根据业务需求限制权限
    return task


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    session: SessionDep, current_user: CurrentUser, task_in: TaskCreate
) -> Any:
    task = Task.from_orm(task_in)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.put("/{id}", response_model=TaskRead)
def update_task(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID, task_in: TaskUpdate
) -> Any:
    task = session.get(Task, id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task_data = task_in.model_dump(exclude_unset=True)
    for key, value in task_data.items():
        setattr(task, key, value)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> None:
    task = session.get(Task, id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()