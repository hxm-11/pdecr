import uuid

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings
from app.models import PdEcrCase, PdEcrModule, User
from app.services.pd_ecr_flowable_service import (
    complete_manager_approval_task,
    start_manager_approval_process,
    sync_approval_task_from_flowable,
)
from app.services.pd_ecr_workflow import (
    approve_case,
    create_approval_task,
    list_my_workflow_tasks,
    reject_case,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def make_user(session: Session, email: str) -> User:
    user = User(
        email=email,
        hashed_password="not-used",
        full_name=email.split("@")[0],
        display_name=email.split("@")[0],
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_case(session: Session, creator: User) -> PdEcrCase:
    case = PdEcrCase(
        case_no=f"PDECR-FLOW-{uuid.uuid4().hex[:6].upper()}",
        title="Flowable approval",
        status="submitted",
        source_type="manual",
        created_by_id=creator.id,
        owner_id=creator.id,
        initiator=creator.email,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def test_start_manager_approval_process_syncs_case_and_task(monkeypatch, session: Session):
    creator = make_user(session, "creator@example.com")
    case = make_case(session, creator)

    monkeypatch.setattr(settings, "FLOWABLE_ENABLED", True)
    monkeypatch.setattr(settings, "FLOWABLE_PROCESS_DEFINITION_KEY", "pd_ecr_manager_approval")

    class FakeClient:
        def start_process_instance(self, process_definition_key, business_key, variables):
            assert process_definition_key == "pd_ecr_manager_approval"
            assert business_key == str(case.id)
            assert variables["caseId"] == str(case.id)
            return {"id": "proc-123", "businessStatus": "running"}

        def get_tasks_for_process_instance(self, process_instance_id):
            assert process_instance_id == "proc-123"
            return [{"id": "task-123", "taskDefinitionKey": "managerApproval"}]

    monkeypatch.setattr(
        "app.services.pd_ecr_flowable_service.FlowableClient",
        lambda: FakeClient(),
    )

    result = start_manager_approval_process(
        case=case,
        approver_id=creator.id,
        approver_email=creator.email,
        approver_name=creator.display_name,
        form_data={"changeSummary": "Adjust tooling"},
    )
    approval_task = create_approval_task(
        session=session,
        case=case,
        approver_id=creator.id,
        approver_email=creator.email,
        approver_name=creator.display_name,
        commit=False,
    )
    sync_approval_task_from_flowable(
        approval_task=approval_task,
        flowable_task=result["task"],
    )
    session.commit()

    assert case.flowable_process_instance_id == "proc-123"
    assert case.flowable_process_definition_key == "pd_ecr_manager_approval"
    assert case.flowable_business_key == str(case.id)
    assert case.flowable_status == "running"
    assert approval_task.flowable_task_id == "task-123"
    assert approval_task.flowable_task_definition_key == "managerApproval"


def test_complete_manager_approval_task_queries_active_task_when_missing(monkeypatch, session: Session):
    creator = make_user(session, "creator2@example.com")
    approver = make_user(session, "approver@example.com")
    case = make_case(session, creator)
    case.flowable_process_instance_id = "proc-456"
    case.flowable_status = "running"
    session.add(case)
    session.commit()

    approval_task = create_approval_task(
        session=session,
        case=case,
        approver_id=approver.id,
        approver_email=approver.email,
        approver_name=approver.display_name,
        commit=True,
    )

    monkeypatch.setattr(settings, "FLOWABLE_ENABLED", True)
    completed: dict[str, object] = {}

    class FakeClient:
        def get_tasks_for_process_instance(self, process_instance_id):
            assert process_instance_id == "proc-456"
            return [{"id": "task-456", "taskDefinitionKey": "managerApproval"}]

        def complete_task(self, task_id, variables):
            completed["task_id"] = task_id
            completed["variables"] = variables
            return {}

    monkeypatch.setattr(
        "app.services.pd_ecr_flowable_service.FlowableClient",
        lambda: FakeClient(),
    )

    complete_manager_approval_task(
        case=case,
        approval_task=approval_task,
        current_user=approver,
        approved=False,
        rejection_reason="Need more evidence",
    )

    assert approval_task.flowable_task_id == "task-456"
    assert case.flowable_status == "rejected"
    assert completed["task_id"] == "task-456"
    assert completed["variables"] == {
        "approved": False,
        "approvedBy": approver.display_name,
        "approvedByEmail": approver.email,
        "rejectionReason": "Need more evidence",
    }


def test_approve_case_updates_module_confirmation_and_flowable_status(session: Session):
    creator = make_user(session, "creator3@example.com")
    approver = make_user(session, "approver3@example.com")
    case = make_case(session, creator)
    module = PdEcrModule(
        case_id=case.id,
        module_id="change-description",
        title="Change Request description",
        content_json={},
        source_cases=[case.case_no],
        source_files=[],
        status="submitted",
    )
    session.add(module)
    session.commit()
    session.refresh(module)

    approval_task = create_approval_task(
        session=session,
        case=case,
        approver_id=approver.id,
        approver_email=approver.email,
        approver_name=approver.display_name,
    )

    approve_case(
        session=session,
        case=case,
        approval_task=approval_task,
        current_user=approver,
        module=module,
        flowable_status="approved",
    )

    assert case.status == "generated"
    assert case.flowable_status == "approved"
    assert module.content_json["leader_confirmed"] is True
    assert module.content_json["leaderConfirmed"] is True
    assert module.content_json["leader_confirmed_by"] == approver.display_name


def test_reject_case_preserves_flowable_status_mirror(session: Session):
    creator = make_user(session, "creator4@example.com")
    approver = make_user(session, "approver4@example.com")
    case = make_case(session, creator)
    approval_task = create_approval_task(
        session=session,
        case=case,
        approver_id=approver.id,
        approver_email=approver.email,
        approver_name=approver.display_name,
    )

    reject_case(
        session=session,
        case=case,
        approval_task=approval_task,
        rejection_reason="Incomplete request",
        flowable_status="rejected",
    )

    assert case.status == "draft"
    assert case.flowable_status == "rejected"
    assert approval_task.status == "rejected"
    assert approval_task.rejection_reason == "Incomplete request"


def test_my_tasks_matches_approval_by_email_when_user_id_is_not_linked(session: Session):
    creator = make_user(session, "creator5@example.com")
    approver = make_user(session, "approver5@example.com")
    case = make_case(session, creator)

    create_approval_task(
        session=session,
        case=case,
        approver_email=approver.email,
        approver_name=approver.display_name,
    )

    tasks = list_my_workflow_tasks(session=session, current_user=approver)

    assert len(tasks["approval_tasks"]) == 1
    assert tasks["approval_tasks"][0]["approver_email"] == approver.email
    assert tasks["approval_tasks"][0]["case"]["case_no"] == case.case_no
