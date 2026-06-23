from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.pd_ecr_case_paths import (
    CURATED_CASES_PATH,
    JIE_JIM_KNOWLEDGE_PDF_DIR,
    iter_safe_text_files,
)
from app.services.pd_ecr_quality import duplicate_case_ids, missing_metadata_fields
from app.services.pd_ecr_schema import (
    HistoricalCase,
    HistoricalMetadata,
    HistoricalModule,
    MODULE_TITLES,
    PdEcrModuleId,
    V1_MODULE_IDS,
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(_clean(item) for item in value if _clean(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    return "" if text in {"-", "N/A", "NA", "None", "null"} else text


def _first(*values: Any) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _safe_json(path: Path) -> Any:
    try:
        return json.loads(_safe_read(path))
    except Exception:
        return None


def _case_code(text: str) -> str:
    match = re.search(r"(PDECR\d{2}[_-]\d{3}|T\d{4})", str(text), re.I)
    return match.group(1).upper().replace("-", "_") if match else ""


def _extract_regex(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            value = re.sub(r"<[^>]+>", " ", match.group(1))
            value = re.sub(r"\s+", " ", value).strip(" |:：")
            if value:
                return value[:500]
    return ""


def _metadata_from_record(record: dict[str, Any], source_file: str, fallback_id: str) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    change_basic = record.get("change_basic") if isinstance(record.get("change_basic"), dict) else {}
    business = record.get("business_fields") if isinstance(record.get("business_fields"), dict) else {}

    case_id = _first(
        record.get("case_id"),
        metadata.get("case_id"),
        record.get("case_no"),
        record.get("id"),
        _case_code(source_file),
        Path(source_file).stem,
        fallback_id,
    )

    customer_project = _first(
        metadata.get("customer_project"),
        record.get("customer_project"),
        record.get("project"),
        record.get("customer"),
    )
    product_no = _first(
        metadata.get("product_no"),
        record.get("product_no"),
        record.get("affected_product_no"),
        business.get("affected_product_no"),
        record.get("product_class"),
    )
    part_no = _first(
        metadata.get("part_no"),
        record.get("part_no"),
        record.get("component_no"),
        record.get("part_number"),
        change_basic.get("change_part_product_name"),
    )

    return {
        "case_id": case_id,
        "dc_no": _first(metadata.get("dc_no"), record.get("dc_no")),
        "mcr_no": _first(metadata.get("mcr_no"), record.get("mcr_no")),
        "change_type": _first(metadata.get("change_type"), record.get("change_type")),
        "product_no": product_no,
        "part_no": part_no,
        "customer_project": customer_project,
        "source_file": source_file,
        "date": _first(metadata.get("date"), record.get("date"), record.get("create_date")),
        "initiator": _first(metadata.get("initiator"), record.get("initiator")),
        "sample_status": _first(metadata.get("sample_status"), record.get("sample_status")),
        "sample_type": _first(metadata.get("sample_type"), record.get("sample_type")),
        "reason_for_change": _first(
            change_basic.get("reason_for_change"),
            record.get("reason_for_change"),
            record.get("change_reason"),
        ),
    }


def _content_from_record(record: dict[str, Any], module_id: PdEcrModuleId, raw_text: str) -> str:
    modules = record.get("modules") if isinstance(record.get("modules"), dict) else {}
    aliases = {
        PdEcrModuleId.BASIC_INFORMATION: ["basic_information", "basic-information", "basic_info"],
        PdEcrModuleId.CHANGE_DESCRIPTION: [
            "change_description",
            "change-description",
            "change_request_description",
            "change_proposal",
        ],
        PdEcrModuleId.REASON_FOR_CHANGE: [
            "reason_for_change",
            "reason-for-change",
            "change_reason",
            "reason",
        ],
        PdEcrModuleId.IMPACT_ANALYSIS: ["impact_analysis", "impact-analysis"],
        PdEcrModuleId.IMPLEMENTATION_PLAN: [
            "implementation_plan",
            "implementation-plan",
            "implementation_task_plan",
            "verification_plan",
        ],
        PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION: [
            "approval_signoff_information",
            "approval-signoff",
            "signature",
            "approval",
        ],
    }
    for key in aliases[module_id]:
        value = modules.get(key, record.get(key))
        if _clean(value):
            return _clean(value)

    if module_id == PdEcrModuleId.CHANGE_DESCRIPTION:
        return _extract_regex(raw_text, [r"(?:Change Request description|Change description|变更描述)[:：\s]*(.+?)(?:\n#{1,6}|\Z)"])
    if module_id == PdEcrModuleId.REASON_FOR_CHANGE:
        return _extract_regex(raw_text, [r"(?:Reason for changes?|Reason of changes?|更改理由|变更原因)[:：\s]*(.+?)(?:\n#{1,6}|\Z)"])
    if module_id == PdEcrModuleId.IMPACT_ANALYSIS:
        return _extract_regex(raw_text, [r"(?:Impact analysis|Affection analysis|影响分析)[:：\s]*(.+?)(?:\n#{1,6}|\Z)"])
    if module_id == PdEcrModuleId.IMPLEMENTATION_PLAN:
        return _extract_regex(raw_text, [r"(?:Implementation task plan|Implementation plan|实施计划)[:：\s]*(.+?)(?:\n#{1,6}|\Z)"])
    if module_id == PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION:
        return _extract_regex(raw_text, [r"(?:Approval|Signature|Sign-off|签字|批准)[:：\s]*(.+?)(?:\n#{1,6}|\Z)"])
    return ""


def _build_modules(record: dict[str, Any], source_file: str, raw_text: str) -> dict[PdEcrModuleId, HistoricalModule]:
    modules: dict[PdEcrModuleId, HistoricalModule] = {}
    for module_id in V1_MODULE_IDS:
        content = _content_from_record(record, module_id, raw_text)
        summary = content[:240] if content else f"No extracted content for {MODULE_TITLES[module_id]}."
        modules[module_id] = HistoricalModule(
            module_id=module_id,
            title=MODULE_TITLES[module_id],
            summary=summary,
            content=content,
            source_file=source_file,
        )
    return modules


def _case_from_record(record: dict[str, Any], source_file: str, raw_text: str = "", fallback_id: str = "") -> HistoricalCase:
    metadata_data = _metadata_from_record(record, source_file, fallback_id)
    metadata = HistoricalMetadata(**metadata_data)
    return HistoricalCase(
        case_id=metadata.case_id,
        metadata=metadata,
        modules=_build_modules(record, source_file, raw_text),
        source_file=source_file,
        source_trace=record.get("source_trace") or {},
        raw_text=raw_text,
        missing_fields=[],
    )


def _load_curated_cases() -> list[HistoricalCase]:
    payload = _safe_json(CURATED_CASES_PATH)
    records = payload if isinstance(payload, list) else payload.get("cases", []) if isinstance(payload, dict) else []
    cases: list[HistoricalCase] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        source_file = _first(record.get("source_file"), record.get("case_no"), f"curated-{index}.json")
        raw_text = json.dumps(record, ensure_ascii=False)
        cases.append(_case_from_record(record, source_file, raw_text, fallback_id=f"curated-{index}"))
    return cases


def _load_jie_jim_metadata_cases() -> list[HistoricalCase]:
    cases: list[HistoricalCase] = []
    if not JIE_JIM_KNOWLEDGE_PDF_DIR.exists():
        return cases
    for metadata_path in sorted(JIE_JIM_KNOWLEDGE_PDF_DIR.glob("*/metadata.json")):
        record = _safe_json(metadata_path)
        if not isinstance(record, dict):
            continue
        cleaned_dir = metadata_path.parent / "cleaned"
        raw_text = "\n\n".join(_safe_read(path) for path in sorted(cleaned_dir.glob("*.md"))) if cleaned_dir.exists() else json.dumps(record, ensure_ascii=False)
        source_file = _first(record.get("source_file"), metadata_path.parent.name)
        cases.append(_case_from_record(record, source_file, raw_text, fallback_id=metadata_path.parent.name))
    return cases


def _load_text_cases(existing_sources: set[str]) -> list[HistoricalCase]:
    cases: list[HistoricalCase] = []
    for path in iter_safe_text_files():
        if path.name in existing_sources or path.name == CURATED_CASES_PATH.name:
            continue
        if path.name.lower() == "metadata.json" and JIE_JIM_KNOWLEDGE_PDF_DIR in path.parents:
            continue
        raw_text = _safe_read(path)
        if not raw_text.strip():
            continue
        record: dict[str, Any] = {}
        if path.suffix.lower() == ".json":
            parsed = _safe_json(path)
            record = parsed if isinstance(parsed, dict) else {}
        record.setdefault("case_id", _case_code(path.name) or path.stem)
        record.setdefault("source_file", path.name)
        record.setdefault("change_description", raw_text[:1200])
        cases.append(_case_from_record(record, path.name, raw_text, fallback_id=path.stem))
    return cases


def load_historical_cases(*, limit: int | None = None, sources: set[str] | None = None) -> list[HistoricalCase]:
    """Load historical PD-ECR cases from configured sources.

    Args:
        limit: Max cases to return (after dedup).
        sources: Optional set of source names to include.
                 Supported: "curated", "jie_jim", "text".
                 When None (default), all sources are included.
    """
    include = (sources or {"curated", "jie_jim", "text"})
    cases: list[HistoricalCase] = []
    if "curated" in include:
        cases.extend(_load_curated_cases())
    if "jie_jim" in include:
        cases.extend(_load_jie_jim_metadata_cases())
    existing_sources = {case.source_file for case in cases}
    if "text" in include:
        cases.extend(_load_text_cases(existing_sources))

    deduped: list[HistoricalCase] = []
    seen: set[str] = set()
    for case in cases:
        key = case.case_id or case.source_file
        if key in seen:
            continue
        seen.add(key)
        deduped.append(case)
        if limit and len(deduped) >= limit:
            break

    duplicates = set(duplicate_case_ids([case.model_dump(mode="json") for case in deduped]))
    qualified: list[HistoricalCase] = []
    for case in deduped:
        missing = missing_metadata_fields(case.metadata.model_dump(mode="json"))
        if case.case_id in duplicates:
            missing.append("duplicate_case_id")
        qualified.append(case.model_copy(update={"missing_fields": missing}))
    return qualified


def find_historical_case(identifier: str) -> HistoricalCase | None:
    needle = str(identifier or "").strip().lower()
    if not needle:
        return None
    needle_code = _case_code(needle).lower()

    for case in load_historical_cases():
        candidates = {
            case.case_id,
            case.metadata.dc_no,
            case.metadata.mcr_no,
            case.source_file,
            Path(case.source_file).stem,
        }
        normalized = {str(value).strip().lower() for value in candidates if value}
        stems = {Path(str(value)).stem.lower() for value in candidates if value}
        codes = {_case_code(str(value)).lower() for value in candidates if value}

        # 1. Exact match
        if needle in normalized:
            return case

        # 2. Prefix / substring match (handles "PDECR24_093_JIM_493" -> "PDECR24_093")
        for n in normalized | stems:
            if n.startswith(needle) or needle.startswith(n):
                return case

        # 3. Case code match (e.g. PDECR24_093 matches PDECR24_093_JIM_493)
        if needle_code and needle_code in codes:
            return case
        for code in codes:
            if code and (code.startswith(needle_code) or needle_code.startswith(code)):
                return case

    return None


def case_to_list_item(case: HistoricalCase) -> dict[str, Any]:
    module_summary = next((module.summary for module in case.modules.values() if module.content), "")
    data = case.model_dump(mode="json")
    data["module_summary"] = module_summary or "No extracted module summary."
    metadata = data["metadata"]
    # 推断来源标签
    source_label = "Knowledge Base"
    source_file = str(case.source_file or "")
    if "pdecr" in source_file.lower() or "jie_jim" in source_file.lower() or "jim" in source_file.lower():
        source_label = "PDECR_JIE_JIM PDF"
    elif source_file.endswith(".json"):
        source_label = "Curated Cases"
    data.update(
        {
            "id": case.case_id,
            "case_no": case.case_id,
            "title": case.case_id,
            "dc_no": metadata.get("dc_no", ""),
            "mcr_no": metadata.get("mcr_no", ""),
            "customer_project": metadata.get("customer_project", ""),
            "customer": metadata.get("customer_project", ""),
            "project": metadata.get("customer_project", ""),
            "product_no": metadata.get("product_no", ""),
            "part_no": metadata.get("part_no", ""),
            "part_number": metadata.get("part_no", ""),
            "change_type": metadata.get("change_type", ""),
            "initiator": metadata.get("initiator", ""),
            "create_date": metadata.get("date", ""),
            "source_file": case.source_file,
            "sample_status": metadata.get("sample_status", ""),
            "sample_type": metadata.get("sample_type", ""),
            "reason_for_change": metadata.get("reason_for_change", ""),
            "from": source_label,
        }
    )
    return data


def case_to_detail(case: HistoricalCase) -> dict[str, Any]:
    data = case.model_dump(mode="json")
    data["modules"] = [module.model_dump(mode="json") for module in case.modules.values()]
    data["case"] = case_to_list_item(case)
    return data


def module_summary(case: HistoricalCase) -> str:
    snippets = []
    for module in case.modules.values():
        if module.summary:
            snippets.append(f"{module.title}: {module.summary}")
        if len(snippets) >= 4:
            break
    return " | ".join(snippets)[:1000] or f"Historical PD-ECR case from {case.source_file}"
