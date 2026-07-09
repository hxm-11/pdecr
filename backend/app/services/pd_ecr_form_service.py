from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "product": ("product", "product_name", "productName", "product_no", "productNo"),
    "customer_project": ("customer_project", "customerProject", "customer", "project", "platform"),
    "change_title": ("change_title", "changeTitle", "title", "change_name", "changeName"),
    "product_no": ("product_no", "productNo", "product_number", "productNumber"),
    "part_no": ("part_no", "partNo", "component_no", "componentNo", "partNumber"),
    "change_reason": ("change_reason", "changeReason", "reason", "reason_for_change", "reasonForChange"),
    "change_description": (
        "change_description",
        "changeDescription",
        "changeSummary",
        "change_proposal",
        "description",
        "summary",
    ),
    "affected_departments": (
        "affected_departments",
        "affectedDepartments",
        "impact_departments",
        "impactDepartments",
        "departments",
        "selected_departments",
        "selectedDepartments",
    ),
}

REQUIRED_NEW_PDECR_FIELDS = (
    "product",
    "customer_project",
    "change_title",
    "product_no",
    "change_reason",
    "change_description",
    "affected_departments",
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _first_value(payload: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for key in aliases:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            return value
        if value is not None and not isinstance(value, (str, list)):
            return value
    return None


def _normalize_departments(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]
    departments: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _clean_text(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        departments.append(text)
    return departments


def normalize_new_pdecr_form(
    *,
    title: str | None = None,
    initiator: str | None = None,
    customer_project: str | None = None,
    product_no: str | None = None,
    part_no: str | None = None,
    target_close_date: str | datetime | None = None,
    form_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(form_data or {})
    explicit = {
        "title": title,
        "initiator": initiator,
        "customer_project": customer_project,
        "product_no": product_no,
        "part_no": part_no,
        "target_close_date": target_close_date,
    }
    for key, value in explicit.items():
        if value is not None and value != "":
            payload.setdefault(key, value)

    normalized: dict[str, Any] = dict(payload)
    for canonical, aliases in FIELD_ALIASES.items():
        value = _first_value(payload, aliases)
        if canonical == "affected_departments":
            normalized[canonical] = _normalize_departments(value)
        else:
            normalized[canonical] = _clean_text(value)

    normalized["title"] = normalized["change_title"] or _clean_text(title)
    normalized["customer_project"] = normalized["customer_project"] or _clean_text(customer_project)
    normalized["product_no"] = normalized["product_no"] or _clean_text(product_no)
    normalized["part_no"] = normalized.get("part_no") or _clean_text(part_no)
    normalized["initiator"] = _clean_text(initiator) or _clean_text(payload.get("initiator"))
    normalized["target_close_date"] = target_close_date or payload.get("target_close_date")
    return normalized


def missing_new_pdecr_fields(normalized_form: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_NEW_PDECR_FIELDS:
        value = normalized_form.get(field)
        if field == "affected_departments":
            if not value:
                missing.append(field)
        elif not _clean_text(value):
            missing.append(field)
    return missing


def validate_new_pdecr_form(normalized_form: dict[str, Any]) -> None:
    missing = missing_new_pdecr_fields(normalized_form)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Missing required PD-ECR form fields",
                "missing_fields": missing,
                "required_fields": list(REQUIRED_NEW_PDECR_FIELDS),
            },
        )


def parse_target_close_date(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = _clean_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid target_close_date. Use ISO date/datetime format.",
        )


def form_contract() -> dict[str, Any]:
    return {
        "required_fields": list(REQUIRED_NEW_PDECR_FIELDS),
        "field_aliases": {key: list(value) for key, value in FIELD_ALIASES.items()},
    }
