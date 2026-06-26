import uuid

from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrCase,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    User,
)


def test_execution_workflow_models_persist_core_fields():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="creator@example.com", hashed_password="x")
        case = PdEcrCase(case_no="PDECR-EXEC-001", title="Execution workflow")
        session.add(user)
        session.add(case)
        session.commit()
        session.refresh(user)
        session.refresh(case)

        visibility = PdEcrDepartmentVisibility(
            case_id=case.id,
            department="quality",
            published_by_id=user.id,
        )
        task = PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="ai-import-28",
            department="quality",
            description="Update testing program on testing equipment",
            assignee_id=user.id,
            assignee_email=user.email,
            assignee_name="Quality Owner",
            status="pending_confirmation",
        )
        session.add(visibility)
        session.add(task)
        session.commit()

        saved_visibility = session.exec(select(PdEcrDepartmentVisibility)).one()
        saved_task = session.exec(select(PdEcrExecutionTask)).one()
        assert saved_visibility.department == "quality"
        assert saved_visibility.visible_to_department is True
        assert saved_task.status == "pending_confirmation"
        assert saved_task.execution_result is None
