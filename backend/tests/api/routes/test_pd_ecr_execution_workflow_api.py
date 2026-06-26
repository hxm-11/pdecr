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
