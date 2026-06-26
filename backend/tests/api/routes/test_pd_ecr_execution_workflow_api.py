import uuid

from fastapi.testclient import TestClient

from app.core.config import settings


def _create_case(client: TestClient, headers: dict[str, str], suffix: str) -> str:
    response = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases",
        headers=headers,
        json={
            "case_no": f"PDECR-API-{suffix}-{uuid.uuid4()}",
            "title": "Execution workflow API",
        },
    )
    assert response.status_code == 200
    return response.json()["case"]["id"]


def test_publish_departments_endpoint_returns_department_alignment(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    case_id = _create_case(client, superuser_token_headers, "PUBLISH")

    response = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/publish-departments",
        headers=superuser_token_headers,
        json={"selected_departments": ["quality"]},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["case"]["status"] == "department_alignment"
    assert content["department_visibility"][0]["department"] == "quality"


def test_assign_execution_endpoint_returns_pending_confirmation_task(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    case_id = _create_case(client, superuser_token_headers, "ASSIGN")
    publish = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/publish-departments",
        headers=superuser_token_headers,
        json={"selected_departments": ["quality"]},
    )
    assert publish.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/assign-execution",
        headers=superuser_token_headers,
        json={
            "assignments": [
                {
                    "checklist_row_id": "ai-import-28",
                    "department": "quality",
                    "description": "Update testing program on testing equipment",
                    "assignee_email": "quality.owner@example.com",
                    "assignee_name": "Quality Owner",
                }
            ]
        },
    )

    assert response.status_code == 200
    content = response.json()
    assert content["case"]["status"] == "assignee_confirmation"
    assert content["execution_tasks"][0]["status"] == "pending_confirmation"


def test_execution_task_endpoints_confirm_complete_and_request_changes(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    case_id = _create_case(client, superuser_token_headers, "TASKS")
    publish = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/publish-departments",
        headers=superuser_token_headers,
        json={"selected_departments": ["quality"]},
    )
    assert publish.status_code == 200
    assign = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/assign-execution",
        headers=superuser_token_headers,
        json={
            "assignments": [
                {
                    "checklist_row_id": "ai-import-28",
                    "department": "quality",
                    "description": "Update testing program on testing equipment",
                    "assignee_email": "quality.owner@example.com",
                    "assignee_name": "Quality Owner",
                }
            ]
        },
    )
    assert assign.status_code == 200
    task_id = assign.json()["execution_tasks"][0]["id"]

    confirm = client.post(
        f"{settings.API_V1_STR}/pd-ecr/workflow/execution-tasks/{task_id}/confirm-assignment",
        headers=superuser_token_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["execution_tasks"][0]["status"] == "in_progress"

    complete = client.post(
        f"{settings.API_V1_STR}/pd-ecr/workflow/execution-tasks/{task_id}/complete",
        headers=superuser_token_headers,
        json={
            "execution_result": "completed",
            "execution_note": "Testing program updated.",
            "evidence_note": "Checked on local tester.",
        },
    )
    assert complete.status_code == 200
    assert complete.json()["case"]["status"] == "leader_review"
    assert complete.json()["execution_tasks"][0]["status"] == "completed"

    request_changes = client.post(
        f"{settings.API_V1_STR}/pd-ecr/workflow/execution-tasks/{task_id}/request-changes",
        headers=superuser_token_headers,
        json={"comment": "Please attach evidence."},
    )
    assert request_changes.status_code == 200
    assert request_changes.json()["case"]["status"] == "changes_requested"
    assert request_changes.json()["execution_tasks"][0]["status"] == "changes_requested"


def test_my_workflow_tasks_endpoint_lists_execution_tasks(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    case_id = _create_case(client, superuser_token_headers, "MYTASKS")
    publish = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/publish-departments",
        headers=superuser_token_headers,
        json={"selected_departments": ["quality"]},
    )
    assert publish.status_code == 200
    assign = client.post(
        f"{settings.API_V1_STR}/pd-ecr/cases/{case_id}/workflow/assign-execution",
        headers=superuser_token_headers,
        json={
            "assignments": [
                {
                    "checklist_row_id": "ai-import-28",
                    "department": "quality",
                    "description": "Update testing program on testing equipment",
                    "assignee_email": "quality.owner@example.com",
                    "assignee_name": "Quality Owner",
                }
            ]
        },
    )
    assert assign.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/pd-ecr/workflow/my-tasks",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    assert any(
        task["case_id"] == case_id and task["checklist_row_id"] == "ai-import-28"
        for task in content["execution_tasks"]
    )
    assert "leader_review_tasks" in content
