from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.pd_ecr_schema import get_required_metadata_keys
from app.services.pd_ecr_schema import HistoricalCase


EMPTY_VALUES = {"", "-", "N/A", "NA", "None", "null", "[]", "{}"}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return not [item for item in value if not is_missing(item)]
    return str(value).strip() in EMPTY_VALUES


def missing_metadata_fields(metadata: dict[str, Any]) -> list[str]:
    return [
        key
        for key in get_required_metadata_keys()
        if key not in metadata or is_missing(metadata.get(key))
    ]


def case_quality_warnings(
    metadata: dict[str, Any],
    *,
    source_path: Path | None = None,
) -> list[str]:
    warnings = [f"Missing metadata: {field}" for field in missing_metadata_fields(metadata)]
    if source_path is not None and not source_path.exists():
        warnings.append(f"Source file not found: {source_path}")
    return warnings


def duplicate_case_ids(cases: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for case in cases:
        case_id = str(case.get("case_id") or "").strip()
        if not case_id:
            continue
        if case_id in seen:
            duplicates.add(case_id)
        seen.add(case_id)
    return sorted(duplicates)


def apply_quality(cases: list[HistoricalCase]) -> list[HistoricalCase]:
    serialized = [case.model_dump(mode="json") for case in cases]
    duplicates = set(duplicate_case_ids(serialized))
    qualified: list[HistoricalCase] = []

    for case in cases:
        missing = missing_metadata_fields(case.metadata.model_dump(mode="json"))
        if case.case_id in duplicates and "duplicate_case_id" not in missing:
            missing.append("duplicate_case_id")
        qualified.append(case.model_copy(update={"missing_fields": missing}))

    return qualified
