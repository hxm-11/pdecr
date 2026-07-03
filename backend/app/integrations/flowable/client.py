from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings


class FlowableClientError(RuntimeError):
    """Raised when Flowable REST calls fail or return invalid data."""


class FlowableClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.FLOWABLE_BASE_URL or "").rstrip("/")
        self.username = username if username is not None else settings.FLOWABLE_USERNAME
        self.password = password if password is not None else settings.FLOWABLE_PASSWORD
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.FLOWABLE_TIMEOUT_SECONDS
        )

    def _auth(self) -> tuple[str, str] | None:
        if not self.username:
            return None
        return (self.username, self.password or "")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        if not self.base_url:
            raise FlowableClientError("FLOWABLE_BASE_URL is not configured")

        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                auth=self._auth(),
            ) as client:
                response = client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise FlowableClientError(
                f"Flowable request failed: {exc.request.method} {exc.request.url} "
                f"returned {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise FlowableClientError(f"Flowable request failed: {exc}") from exc

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise FlowableClientError(
                f"Flowable response was not valid JSON for {method} {path}"
            ) from exc

    @staticmethod
    def _serialize_variable(name: str, value: Any) -> dict[str, Any]:
        payload = {"name": name, "value": value}
        if value is None:
            return payload
        if isinstance(value, bool):
            payload["type"] = "boolean"
        elif isinstance(value, int) and not isinstance(value, bool):
            payload["type"] = "integer"
        elif isinstance(value, float):
            payload["type"] = "double"
        else:
            payload["type"] = "string"
        return payload

    def _serialize_variables(self, variables: dict[str, Any] | None) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for name, value in (variables or {}).items():
            serialized.append(self._serialize_variable(name, value))
        return serialized

    def deploy_process_definition(self, bpmn_file_path: str):
        file_path = Path(bpmn_file_path)
        if not file_path.exists():
            raise FlowableClientError(f"BPMN file not found: {bpmn_file_path}")

        with file_path.open("rb") as handle:
            return self._request(
                "POST",
                "/repository/deployments",
                data={"deploymentKey": file_path.stem},
                files={
                    "file": (
                        file_path.name,
                        handle,
                        "application/octet-stream",
                    )
                },
            )

    def start_process_instance(
        self,
        process_definition_key: str,
        business_key: str,
        variables: dict,
    ):
        return self._request(
            "POST",
            "/runtime/process-instances",
            json={
                "processDefinitionKey": process_definition_key,
                "businessKey": business_key,
                "variables": self._serialize_variables(variables),
            },
        )

    def get_tasks_by_assignee(self, user_id: str):
        return self._request(
            "GET",
            "/runtime/tasks",
            params={"assignee": user_id},
        ).get("data", [])

    def get_tasks_by_candidate_group(self, group_id: str):
        return self._request(
            "GET",
            "/runtime/tasks",
            params={"candidateGroup": group_id},
        ).get("data", [])

    def query_tasks(self, **filters: Any):
        payload = {key: value for key, value in filters.items() if value not in (None, "")}
        return self._request("POST", "/query/tasks", json=payload).get("data", [])

    def get_tasks_for_process_instance(self, process_instance_id: str):
        return self.query_tasks(processInstanceId=process_instance_id)

    def get_task(self, task_id: str):
        return self._request("GET", f"/runtime/tasks/{task_id}")

    def complete_task(self, task_id: str, variables: dict):
        return self._request(
            "POST",
            f"/runtime/tasks/{task_id}",
            json={
                "action": "complete",
                "variables": self._serialize_variables(variables),
            },
        )

    def claim_task(self, task_id: str, user_id: str):
        return self._request(
            "POST",
            f"/runtime/tasks/{task_id}",
            json={"action": "claim", "assignee": user_id},
        )

    def get_process_instance(self, process_instance_id: str):
        return self._request(
            "GET",
            f"/runtime/process-instances/{process_instance_id}",
        )

    def get_historic_tasks(self, process_instance_id: str):
        return self._request(
            "GET",
            "/history/historic-task-instances",
            params={"processInstanceId": process_instance_id},
        ).get("data", [])
