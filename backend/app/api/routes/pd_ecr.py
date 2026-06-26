import difflib
import hashlib
import json
import logging
import os
import re
import sqlite3
import time as _time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from jinja2 import BaseLoader, Environment
import markdown
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlmodel import select

from app.rag.retriever import retrieve_pd_ecr_context, retrieve_pd_ecr_results
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    PdEcrCaseCreate,
    PdEcrCaseUpdate,
    PdEcrActivity,
    PdEcrCommentCreate,
    PdEcrModuleUpdate,
    PdEcrStagedDocument,
    PdEcrStagedDocumentUpdate,
    PdEcrTaskCreate,
    PdEcrVersion,
)
from app.services.pd_ecr_case_service import (
    assign_module,
    create_case,
    create_comment,
    create_task,
    ensure_case_manage_access,
    get_case_or_404,
    list_cases as list_db_cases,
    list_modules,
    serialize_case,
    serialize_module,
    transition_case,
    update_case,
    update_module,
)
from app.services.pd_ecr_notification_service import (
    run_due_reminders,
    send_module_assignment_email,
)
from app.services.pd_ecr_workflow import (
    assign_execution_tasks,
    complete_execution_task,
    confirm_department_task,
    confirm_execution_assignment,
    get_workflow_state,
    publish_case_to_departments,
    request_department_changes,
    request_execution_task_changes,
    review_leader_task,
    submit_for_department_confirmation,
)
from app.services.pd_ecr_ai_case_service import (
    apply_generated_module,
    create_case_from_ai,
    regenerate_module_preview,
)
from app.services.pd_ecr_export_service import export_case
from app.services.pd_ecr_case_loader import (
    case_to_detail,
    case_to_list_item,
    find_historical_case,
    load_historical_cases,
)
from app.services.pd_ecr_export import export_v1_draft
from app.services.pd_ecr_generation import generate_grounded_draft, get_cached_draft
from app.services.pd_ecr_import_service import import_historical_sources, ingest_uploaded_file
from app.services.pd_ecr_realtime_service import pd_ecr_connection_manager
from app.services.pd_ecr_retrieval import retrieve_similar_cases
from app.services.pd_ecr_schema import GeneratedDraft, NewPdEcrRequest

load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)
DEBUG_PD_ECR = os.getenv("PD_ECR_DEBUG") == "1"


def debug_print(*args):
    if DEBUG_PD_ECR:
        logger.debug(" ".join(str(arg) for arg in args))

DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "pd_ecr_cases" / "pd_ecr_cases.json"
)

CASE_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "pd_ecr_cases" / "pd_ecr_cases.json"
DRAFT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pd_ecr_cases" / "pd_ecr_module_drafts.sqlite3"
PDECR_JIE_JIM_PDF_DIR = Path(__file__).resolve().parents[2] / "rag" / "PDECR_JIE_JIM"
JIE_JIM_METADATA_DIR = Path(__file__).resolve().parents[2] / "rag" / "jie_jim_knowledge_pdf"


class PdEcrModuleDraftPayload(BaseModel):
    record_id: str
    module_id: str
    data: Dict[str, Any]
    title: str = ""


class PdEcrModuleAssignmentPayload(BaseModel):
    assignee_id: uuid.UUID | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    department: str | None = None
    due_date: datetime | None = None
    reminder_policy: Dict[str, Any] | None = None
    send_assignment_email: bool = True


class PdEcrTransitionPayload(BaseModel):
    status: str


class PdEcrWorkflowSubmitPayload(BaseModel):
    selected_departments: list[str]
    assignees: Dict[str, Dict[str, Any]] | None = None



class PdEcrPublishDepartmentsPayload(BaseModel):
    selected_departments: list[str]


class PdEcrExecutionAssignmentPayload(BaseModel):
    checklist_row_id: str
    department: str
    description: str = ""
    assignee_id: uuid.UUID | None = None
    assignee_email: str
    assignee_name: str | None = None
    due_date: datetime | None = None


class PdEcrAssignExecutionPayload(BaseModel):
    assignments: list[PdEcrExecutionAssignmentPayload]


class PdEcrExecutionCompletePayload(BaseModel):
    execution_result: str
    execution_note: str | None = None
    evidence_note: str | None = None

class PdEcrDepartmentTaskConfirmPayload(BaseModel):
    impact_result: str
    impact_remark: str | None = None
    action_required: str | None = None


class PdEcrWorkflowCommentPayload(BaseModel):
    comment: str


class PdEcrLeaderReviewPayload(BaseModel):
    decision: str
    review_comment: str | None = None
    signature_name: str | None = None


class PdEcrImportPayload(BaseModel):
    limit: int | None = None


class PdEcrExportPayload(BaseModel):
    format: str = "html"
    draft_id: str | None = None
    draft: Dict[str, Any] | None = None


class PdEcrRetrievePayload(BaseModel):
    input: Dict[str, Any] | None = None
    top_k: int = 5
    filters: Dict[str, Any] | None = None


class PdEcrGenerateDraftPayload(BaseModel):
    case_id: str | None = None
    input: Dict[str, Any]
    similar_cases: list[Dict[str, Any]] | None = None


class PdEcrGenerateCasePayload(BaseModel):
    input: Dict[str, Any]
    similar_cases: list[Dict[str, Any]] | None = None


class PdEcrRegenerateModulePayload(BaseModel):
    instruction: str | None = None


class PdEcrApplyGeneratedModulePayload(BaseModel):
    generated: Dict[str, Any]
    expected_version: int


class PdEcrV1ExportPayload(BaseModel):
    draft_id: str
    format: str = "html"
    draft: Dict[str, Any] | None = None


def get_draft_db_connection() -> sqlite3.Connection:
    DRAFT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DRAFT_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS pd_ecr_module_draft (
            record_id TEXT NOT NULL,
            module_id TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (record_id, module_id)
        )
        """
    )
    # Migration: add title and created_at columns if they don't exist yet
    for column, col_def in [
        ("title", "TEXT NOT NULL DEFAULT ''"),
        ("created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ]:
        try:
            connection.execute(
                f"ALTER TABLE pd_ecr_module_draft ADD COLUMN {column} {col_def}"
            )
        except sqlite3.OperationalError:
            pass  # column already exists
    # Backfill created_at for existing rows
    connection.execute(
        "UPDATE pd_ecr_module_draft SET created_at = updated_at "
        "WHERE created_at = '' OR created_at IS NULL"
    )
    return connection


def _parse_draft_data(data_text: str) -> dict:
    try:
        return json.loads(data_text)
    except json.JSONDecodeError:
        return {}


def format_case_field(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback

    if isinstance(value, list):
        values = [format_case_field(item, "") for item in value]
        text = " / ".join(item for item in values if item)
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value).strip()

    return text if text and text not in {"N/A", "NA", "null", "None"} else fallback


def clean_extracted_case_field(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" |:：")

    stop_markers = [
        "Reason of changes",
        "Reason for changes",
        "更改理由",
        "Step 2",
        "Change proposal",
        "Sample type",
        "样品类型",
    ]
    for marker in stop_markers:
        index = text.lower().find(marker.lower())
        if index > 0:
            text = text[:index].strip(" |:：")

    return text or "-"


def extract_first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            value = clean_extracted_case_field(match.group(1))
            if value != "-":
                return value
    return "-"


def extract_initiator_from_text(text: str) -> str:
    return extract_first_match(
        text,
        [
            r"Initiator\s*/\s*发起人\s*[:：]?\s*(?:\|)?\s*([^<\n\r]+)",
            r"发起人\s*[:：]?\s*(?:\|)?\s*([^<\n\r]+)",
            r"Initiator\s*[:：]?\s*(?:\|)?\s*([^<\n\r]+)",
        ],
    )


def extract_department_from_initiator(initiator: str) -> str:
    match = re.search(r"\(([^)]+)\)", str(initiator or ""))
    return match.group(1).strip() if match else "-"


def load_parsed_case_json(path: Path) -> Dict[str, Any]:
    parsed_dir = path.parent / "parsed" / "json"
    case_code = extract_case_code(path.name)

    if not parsed_dir.exists() or not case_code:
        return {}

    for json_path in sorted(parsed_dir.glob("*.json")):
        if extract_case_code(json_path.name) != case_code:
            continue

        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    return {}


def build_knowledge_case_record(path: Path, case_id: int) -> Dict[str, Any]:
    parsed = load_parsed_case_json(path)
    metadata = parsed.get("metadata") or {}
    business_fields = parsed.get("business_fields") or {}

    try:
        source_text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        source_text = ""

    customer_project = metadata.get("customer_project")
    initiator = (
        format_case_field(metadata.get("initiator"), "")
        or format_case_field(business_fields.get("responsible_person"), "")
        or extract_initiator_from_text(source_text)
    )
    if not initiator:
        initiator = "-"

    project = format_case_field(customer_project)
    department = (
        format_case_field(business_fields.get("responsible_department"), "")
        or extract_department_from_initiator(initiator)
        or "-"
    )
    title = re.sub(r"^T\d{4}[-_\s]*", "", path.stem, flags=re.I).strip() or path.stem

    return {
        "id": case_id,
        "case_no": path.stem,
        "title": title,
        "dc_no": format_case_field(metadata.get("dc_no"), ""),
        "date": format_case_field(metadata.get("date"), ""),
        "create_date": format_case_field(metadata.get("date")),
        "product_class": "PD-ECR",
        "customer": project,
        "project": project,
        "customer_project": project,
        "part_number": format_case_field(metadata.get("component_no")),
        "component_no": format_case_field(metadata.get("component_no"), ""),
        "product_no": format_case_field(metadata.get("affected_product_no"), ""),
        "initiator": initiator,
        "department": department,
        "source_file": path.name,
    }


def extract_pdecr_case_code(name: str) -> str:
    text = str(name or "")
    match = re.search(r"(PDECR\d{2}[_-]\d{3})", text, re.I)
    if not match:
        return ""
    return match.group(1).upper().replace("-", "_")


def load_jie_jim_metadata_index() -> Dict[str, Dict[str, Any]]:
    metadata_index: Dict[str, Dict[str, Any]] = {}
    if not JIE_JIM_METADATA_DIR.exists():
        return metadata_index

    for metadata_path in sorted(JIE_JIM_METADATA_DIR.glob("*/metadata.json")):
        try:
            metadata_record = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as e:
            debug_print("PD-ECR metadata read failed:", metadata_path, e)
            continue

        if not isinstance(metadata_record, dict):
            continue

        metadata_record["_metadata_file"] = str(
            metadata_path.relative_to(Path(__file__).resolve().parents[2])
        )
        for candidate in [
            metadata_record.get("case_id"),
            metadata_record.get("source_file"),
            metadata_path.parent.name,
        ]:
            case_code = extract_pdecr_case_code(str(candidate or ""))
            if case_code:
                metadata_index[case_code] = metadata_record

    return metadata_index


def build_pdecr_pdf_case_record(
    path: Path,
    metadata_record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    case_no = path.stem
    case_id = (
        format_case_field(metadata_record.get("case_id"), "")
        if metadata_record
        else ""
    ) or extract_pdecr_case_code(path.name) or case_no
    metadata_record = metadata_record or {}
    metadata = metadata_record.get("metadata") or {}
    change_basic = metadata_record.get("change_basic") or {}
    search_text = read_pdecr_pdf_search_text(path, metadata_record)

    customer_project = format_case_field(metadata.get("customer_project"))
    sample_status = format_case_field(metadata.get("sample_status"), "")
    part_number = format_case_field(
        change_basic.get("change_part_product_name")
        or metadata.get("part_no")
        or metadata.get("product_no")
    )

    return {
        "id": case_no,
        "case_no": case_no,
        "case_id": case_id,
        "title": case_no,
        "dc_no": format_case_field(metadata.get("dc_no"), ""),
        "mcr_no": format_case_field(metadata.get("mcr_no"), ""),
        "date": format_case_field(metadata.get("date"), ""),
        "create_date": format_case_field(metadata.get("date")),
        "product_class": sample_status or "PD-ECR",
        "from": "PDECR_JIE_JIM PDF",
        "customer": customer_project,
        "project": customer_project,
        "customer_project": customer_project,
        "part_number": part_number,
        "product_no": format_case_field(metadata.get("product_no"), ""),
        "part_no": format_case_field(metadata.get("part_no"), ""),
        "change_type": format_case_field(metadata.get("change_type"), ""),
        "sample_status": sample_status,
        "sample_type": format_case_field(metadata.get("sample_type"), ""),
        "initiator": format_case_field(metadata.get("initiator")),
        "department": "-",
        "source_file": path.name,
        "metadata_source_file": format_case_field(metadata_record.get("source_file"), ""),
        "metadata_file": format_case_field(metadata_record.get("_metadata_file"), ""),
        "reason_for_change": format_case_field(change_basic.get("reason_for_change"), ""),
        "change_source": format_case_field(change_basic.get("change_source"), ""),
        "pdf_file": path.name,
        "pdf_url": f"/api/v1/pd-ecr/pdf/{quote(path.name)}",
        "link": "Open modules",
        "docling_source_file": f"docling_output/{path.stem}_docling.md",
        "search_text_preview": search_text[:800],
    }


def list_pdecr_pdf_case_records() -> list[Dict[str, Any]]:
    metadata_index = load_jie_jim_metadata_index()
    return [
        build_pdecr_pdf_case_record(
            path,
            metadata_index.get(extract_pdecr_case_code(path.name)),
        )
        for path in sorted(PDECR_JIE_JIM_PDF_DIR.glob("*.pdf"))
    ]


def find_pdecr_pdf_case_record(identifier: str) -> Dict[str, Any] | None:
    requested = str(identifier or "").strip()
    if not requested:
        return None
    requested_lower = requested.lower()
    requested_stem = Path(requested).stem.lower()
    requested_code = extract_pdecr_case_code(requested).lower()
    for record in list_pdecr_pdf_case_records():
        candidates = {
            str(record.get("id") or ""),
            str(record.get("case_no") or ""),
            str(record.get("case_id") or ""),
            str(record.get("source_file") or ""),
            str(record.get("pdf_file") or ""),
        }
        stems = {Path(candidate).stem for candidate in candidates if candidate}
        codes = {extract_pdecr_case_code(candidate) for candidate in candidates}
        normalized = {candidate.lower() for candidate in candidates if candidate}
        normalized.update(stem.lower() for stem in stems if stem)
        normalized.update(code.lower() for code in codes if code)
        if (
            requested_lower in normalized
            or requested_stem in normalized
            or (requested_code and requested_code in normalized)
        ):
            return record
    return None


def read_pdecr_pdf_search_text(
    pdf_path: Path,
    metadata_record: Dict[str, Any] | None = None,
) -> str:
    docling_dir = PDECR_JIE_JIM_PDF_DIR / "docling_output"
    candidates = [
        docling_dir / f"{pdf_path.stem}_docling.md",
        docling_dir / f"{pdf_path.stem}_docling.json",
    ]
    text_parts = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            debug_print("PD-ECR docling search text read failed:", path, e)
    if metadata_record:
        text_parts.append(json.dumps(metadata_record, ensure_ascii=False))
    return "\n\n".join(text_parts)


def _fuzzy_score(text: str, query: str, threshold: float = 0.45) -> float:
    """Return a fuzzy match score (0–1) for query against text, or 0 if below threshold."""
    text_lower = text.lower()
    query_lower = query.lower()
    if len(query_lower) < 2:
        return 0.0

    # Quick exact check
    if query_lower in text_lower:
        return 1.0

    # Sliding window: compare query against every same-length substring of text
    qlen = len(query_lower)
    tlen = len(text_lower)
    if qlen > tlen:
        # Shorter text: check if text is a subsequence of query
        ratio = difflib.SequenceMatcher(None, text_lower, query_lower).ratio()
        return ratio if ratio >= threshold else 0.0

    best = 0.0
    # Sample windows to keep performance reasonable on long texts
    step = max(1, (tlen - qlen) // 200) if (tlen - qlen) > 200 else 1
    for i in range(0, tlen - qlen + 1, step):
        window = text_lower[i : i + qlen]
        ratio = difflib.SequenceMatcher(None, window, query_lower).ratio()
        if ratio > best:
            best = ratio
            if best >= 0.95:  # early exit on near-perfect match
                break

    return best if best >= threshold else 0.0


def _extract_search_query(user_input: Dict[str, Any]) -> str:
    """Extract only the userʼs actual search text, ignoring metadata wrapper fields."""
    # Priority fields that contain the real user query
    search_fields = ["reason", "change_proposal", "description", "query", "text", "search"]
    parts = []
    for key in search_fields:
        value = str(user_input.get(key, "")).strip()
        if value and len(value) > 3:
            parts.append(value)
    # If nothing found in known search fields, fall back to all non-metadata values
    if not parts:
        for key, value in (user_input or {}).items():
            if key in {"dc_no", "date", "customer_project", "remarks", "initiator", "source"}:
                continue
            text = str(value).strip()
            if text and len(text) > 3:
                parts.append(text)
    return " ".join(parts)


def search_pdecr_pdf_case_records(
    user_input: Dict[str, Any],
    top_k: int = 20,
) -> list[Dict[str, Any]]:
    cases = list_pdecr_pdf_case_records()
    query_text = _extract_search_query(user_input).strip()
    if not query_text:
        return []

    query_lower = query_text.lower()
    tokens = [
        token
        for token in re.split(r"[\s,;，；、/|:：()（）]+", query_lower)
        if len(token) >= 2
    ]

    scored_cases = []
    for case in cases:
        # Extract key fields for targeted matching
        reason = str(case.get("reason_for_change") or "").lower()
        change_type = str(case.get("change_type") or "").lower()

        # Build searchable text: reason_for_change gets highest weight
        pdf_path = PDECR_JIE_JIM_PDF_DIR / str(case.get("pdf_file") or "")
        pdf_text = read_pdecr_pdf_search_text(pdf_path).lower()
        metadata_text = json.dumps(case, ensure_ascii=False).lower()

        score = 0.0
        matched_keywords = []

        # --- Tier 1: reason_for_change field (highest weight) ---
        for token in tokens:
            if token in reason:
                score += 10.0 + min(len(token), 15)
                matched_keywords.append(f"reason:{token}")
            else:
                fuzzy = _fuzzy_score(reason, token)
                if fuzzy >= 0.5:
                    score += 8.0 * fuzzy
                    matched_keywords.append(f"reason:{token}~")

        # --- Tier 2: change_type field ---
        for token in tokens:
            if token in change_type:
                score += 5.0
                matched_keywords.append(f"type:{token}")
            else:
                fuzzy = _fuzzy_score(change_type, token)
                if fuzzy >= 0.5:
                    score += 3.0 * fuzzy
                    matched_keywords.append(f"type:{token}~")

        # --- Tier 3: full text search (PDF + metadata) ---
        full_text = metadata_text + "\n\n" + pdf_text
        for token in tokens:
            if token in full_text:
                score += 2.0
                matched_keywords.append(token)
            else:
                fuzzy = _fuzzy_score(full_text, token)
                if fuzzy >= 0.6:
                    score += 1.5 * fuzzy
                    matched_keywords.append(f"{token}~")

        # --- Tier 4: full query phrase match against reason_for_change ---
        if query_lower in reason:
            score += 25.0
            matched_keywords.append("phrase:reason")
        elif len(query_lower) > 8:
            fuzzy = _fuzzy_score(reason, query_lower)
            if fuzzy >= 0.35:
                score += 15.0 * fuzzy
                matched_keywords.append("phrase:reason~")

        if score <= 0:
            continue

        scored_case = dict(case)
        scored_case["score"] = round(score, 1)
        scored_case["matched_keywords"] = sorted(set(matched_keywords))
        scored_case["search_text_preview"] = pdf_text[:800]
        scored_cases.append(scored_case)

    scored_cases.sort(
        key=lambda item: (
            float(item.get("score") or 0),
            str(item.get("create_date") or ""),
            str(item.get("case_no") or ""),
        ),
        reverse=True,
    )
    return scored_cases[:top_k]


# Knowledge 目录扫描缓存（60 秒 TTL，避免每次请求都 glob + 读文件）
_knowledge_scan_cache: Dict[str, Any] | None = None
_knowledge_scan_cache_ts: float = 0.0
_KNOWLEDGE_SCAN_CACHE_TTL = 60  # 秒


def _enrich_cases_with_pdf_urls(cases: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """为每个 case 补充 pdf_url / pdf_file，如果 PDECR_JIE_JIM_PDF_DIR 下存在对应 PDF。"""
    if not PDECR_JIE_JIM_PDF_DIR.exists():
        return cases

    pdf_files = sorted(PDECR_JIE_JIM_PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        return cases

    pdf_map: Dict[str, Path] = {}
    for pdf_path in pdf_files:
        pdf_map[pdf_path.stem.lower()] = pdf_path
        code = extract_pdecr_case_code(pdf_path.name).lower()
        if code:
            pdf_map[code] = pdf_path

    for case in cases:
        if case.get("pdf_url") and case.get("pdf_file"):
            continue

        case_id = str(case.get("case_id") or case.get("case_no") or case.get("id") or "")
        source_file = str(case.get("source_file") or "")
        candidates = [
            case_id,
            Path(source_file).stem if source_file else "",
            extract_pdecr_case_code(case_id),
            extract_pdecr_case_code(source_file),
        ]

        matched = None
        for candidate in candidates:
            candidate_lower = candidate.strip().lower()
            if not candidate_lower:
                continue
            if candidate_lower in pdf_map:
                matched = pdf_map[candidate_lower]
                break
            # 模糊匹配：PDF 文件名 startswith candidate
            for stem, pdf_path in pdf_map.items():
                if stem.startswith(candidate_lower) or candidate_lower in stem:
                    matched = pdf_path
                    break
            if matched:
                break

        if matched:
            case["pdf_file"] = matched.name
            case["pdf_url"] = f"/api/v1/pd-ecr/pdf/{quote(matched.name)}"
            case["link"] = "Open PDF"
            case["from"] = case.get("from") or "PDECR_JIE_JIM PDF"

    return cases


@router.get("/cases")
def list_pd_ecr_cases(
    session: SessionDep,
    status: str | None = None,
    query: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    global _knowledge_scan_cache, _knowledge_scan_cache_ts
    all_cases: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _dedup_keys(case: dict[str, Any]) -> set[str]:
        """Build multiple dedup keys for a case so the same record from
        different sources (with different case_no formatting) is recognised.

        Priority of key types:
        1. PDECR case code extracted from case_no (e.g. PDECR24_093)
        2. T-code extracted from case_no (e.g. T0001)
        3. Exact case_no (lowercased)
        4. Source file / PDF file stem
        5. Raw id fallback
        """
        keys: set[str] = set()

        case_no = str(case.get("case_no") or "").strip()
        source_file = str(case.get("source_file") or case.get("pdf_file") or "").strip()

        # ── PDECR code (most reliable cross-source identifier) ──
        pdecr_code = extract_pdecr_case_code(case_no) if case_no else ""
        if pdecr_code:
            keys.add(f"pdecr:{pdecr_code.lower()}")
        if source_file:
            sf_pdecr = extract_pdecr_case_code(source_file)
            if sf_pdecr:
                keys.add(f"pdecr:{sf_pdecr.lower()}")

        # ── T-code (T0001-style) ──
        t_code = extract_case_code(case_no) if case_no else ""
        if t_code:
            keys.add(f"tc:{t_code.lower()}")
        if source_file:
            sf_tcode = extract_case_code(source_file)
            if sf_tcode:
                keys.add(f"tc:{sf_tcode.lower()}")

        # ── Exact case_no ──
        if case_no:
            keys.add(f"cn:{case_no.lower()}")

        # ── Source file stem ──
        if source_file:
            keys.add(f"sf:{Path(source_file).stem.lower()}")

        # ── Raw id (last resort) ──
        raw_id = str(case.get("id") or "")
        if raw_id:
            keys.add(f"id:{raw_id.lower()}")

        return keys

    def _add_cases(incoming: list[dict[str, Any]], source_label: str) -> None:
        for case in incoming:
            keys = _dedup_keys(case)
            if keys & seen:  # any intersection → duplicate
                continue
            seen.update(keys)
            case["_source"] = source_label
            all_cases.append(case)

    # ── Source 1: V1 normalized files ──
    try:
        normalized = [
            case_to_list_item(case)
            for case in load_historical_cases(sources={"jie_jim"})
        ]
        normalized = _enrich_cases_with_pdf_urls(normalized)
        _add_cases(normalized, "v1_normalized_files")
    except Exception as e:
        debug_print("PD-ECR V1 case loader fallback:", e)

    # ── Source 2: PDECR_JIE_JIM PDF directory ──
    if PDECR_JIE_JIM_PDF_DIR.exists():
        try:
            pdf_cases = list_pdecr_pdf_case_records()
            _add_cases(pdf_cases, "pdecr_jie_jim_pdf")
        except Exception as e:
            debug_print("PD-ECR PDF case loader fallback:", e)

    # ── Source 3: PostgreSQL / SQLite database ──
    try:
        db_cases = list_db_cases(
            session=session,
            status_filter=status,
            query=None,  # query applied later on merged set
            skip=0,
            limit=10000,
        )
        _add_cases(
            [serialize_case(case) for case in db_cases],
            "database",
        )
    except Exception as e:
        debug_print("PD-ECR database case list fallback:", e)

    # ── Source 4: JSON file + knowledge directory (with cache) ──
    now = _time.time()
    if _knowledge_scan_cache is not None and (now - _knowledge_scan_cache_ts) < _KNOWLEDGE_SCAN_CACHE_TTL:
        _add_cases(_knowledge_scan_cache.get("cases", []), "knowledge_cache")
    else:
        json_cases: list[Dict[str, Any]] = []
        if DATA_PATH.exists():
            try:
                with DATA_PATH.open("r", encoding="utf-8") as f:
                    json_cases = json.load(f)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"读取 PD-ECR cases 失败：{e}")

        knowledge_dir = Path(__file__).resolve().parents[2] / "rag" / "knowledge"
        existing_sources = {
            str(item.get("source_file") or item.get("case_no") or "").strip()
            for item in json_cases
            if isinstance(item, dict)
        }
        existing_case_codes = {
            extract_case_code(str(item.get("source_file") or item.get("case_no") or ""))
            for item in json_cases
            if isinstance(item, dict)
        }

        if knowledge_dir.exists():
            next_id = len(json_cases) + 1
            for path in sorted(knowledge_dir.glob("*.md")):
                if "_signature_structured" in path.stem:
                    continue
                case_code = extract_case_code(path.name)
                if path.name in existing_sources or (case_code and case_code in existing_case_codes):
                    continue
                json_cases.append(build_knowledge_case_record(path, next_id))
                next_id += 1

        _knowledge_scan_cache = {"cases": json_cases}
        _knowledge_scan_cache_ts = now
        _add_cases(json_cases, "knowledge_files")

    # ── Query filter ──
    lowered_query = (query or "").strip().lower()
    if lowered_query:
        all_cases = [
            case
            for case in all_cases
            if lowered_query in json.dumps(case, ensure_ascii=False).lower()
        ]

    return {
        "cases": all_cases[skip : skip + limit],
        "total": len(all_cases),
    }


def _find_pdf_fuzzy(requested_name: str, *search_dirs: Path) -> Path | None:
    """在多个目录中模糊查找 PDF 文件。"""
    requested_stem = Path(requested_name).stem.lower()
    requested_code = extract_pdecr_case_code(requested_name).lower()

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # 先在目录下直接查找 *.pdf
        for pdf_path in sorted(search_dir.glob("*.pdf")):
            pdf_stem = pdf_path.stem.lower()
            # 精确匹配
            if pdf_stem == requested_stem:
                return pdf_path
            # 前缀匹配
            if pdf_stem.startswith(requested_stem) or requested_stem.startswith(pdf_stem):
                return pdf_path
            # PDECR 编号匹配
            pdf_code = extract_pdecr_case_code(pdf_path.name).lower()
            if requested_code and pdf_code == requested_code:
                return pdf_path

        # 再在子目录中递归查找
        for pdf_path in sorted(search_dir.rglob("*.pdf")):
            pdf_stem = pdf_path.stem.lower()
            if pdf_stem == requested_stem:
                return pdf_path
            if pdf_stem.startswith(requested_stem) or requested_stem.startswith(pdf_stem):
                return pdf_path
            pdf_code = extract_pdecr_case_code(pdf_path.name).lower()
            if requested_code and pdf_code == requested_code:
                return pdf_path

    return None


@router.get("/pdf/{filename}")
def get_pdecr_jie_jim_pdf(filename: str):
    safe_name = Path(filename).name

    # 搜索顺序：PDECR_JIE_JIM 目录 → jie_jim_knowledge_pdf 子目录
    pdf_path = _find_pdf_fuzzy(safe_name, PDECR_JIE_JIM_PDF_DIR, JIE_JIM_METADATA_DIR)

    if pdf_path is None:
        raise HTTPException(status_code=404, detail=f"PD-ECR PDF not found: {safe_name}")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="inline",
    )


STRUCTURED_SIGNATURE_DIR = Path(__file__).resolve().parents[2] / "rag" / "knowledge"


BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "templates_pre"
REPORTS_DIR = BASE_DIR / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODULE_TEMPLATE_MAP = {
    "change-description": {
        "title": "变更描述",
        "template_file": "1change_description.md",
    },
    "impact-analysis": {
        "title": "影响分析",
        "template_file": "2impact.md",
    },
    "validation-plan": {
        "title": "验证计划",
        "template_file": "3validation_plan.md",
    },
    "validation-result": {
        "title": "验证结果",
        "template_file": "4Valiation_result.md",
    },
    "implementation-plan": {
        "title": "实施计划",
        "template_file": "5implementation_plan.md",
    },
    "implementation-result": {
        "title": "实施结果",
        "template_file": "6Implementation_result.md",
    },
}


def render_template_file(template_file: str, context: dict) -> str:
    template_path = TEMPLATES_DIR / template_file

    if not template_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"模板文件不存在：{template_path}",
        )

    try:
        template_text = template_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"模板文件读取失败：{template_file}，错误：{str(e)}",
        )

    try:
        env = Environment(loader=BaseLoader(), autoescape=False)
        template = env.from_string(template_text)
        return template.render(**context)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"模板渲染失败：{template_file}，错误：{str(e)}",
        )


def _template_context_for_history(
    user_input: Dict[str, Any] | None = None,
    *,
    content: str = "",
    case_record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    user_input = user_input or {}
    case_record = case_record or {}
    component_no = (
        user_input.get("component_no")
        or user_input.get("part_no")
        or case_record.get("part_no")
        or case_record.get("part_number")
        or ""
    )
    basic_info = {
        "dc_no": user_input.get("dc_no")
        or case_record.get("dc_no")
        or case_record.get("case_id")
        or "",
        "date": user_input.get("date")
        or case_record.get("date")
        or case_record.get("create_date")
        or "",
        "customer_project": user_input.get("customer_project")
        or case_record.get("customer_project")
        or case_record.get("project")
        or "",
        "mcr_no": user_input.get("mcr_no") or case_record.get("mcr_no") or "",
        "product_no": user_input.get("product_no")
        or case_record.get("product_no")
        or "",
        "component_no": component_no,
        "initiator": user_input.get("initiator")
        or case_record.get("initiator")
        or "",
    }
    change_reason = (
        user_input.get("change_reason")
        or user_input.get("reason")
        or case_record.get("reason_for_change")
        or ""
    )
    change_description = (
        user_input.get("change_description")
        or user_input.get("change_proposal")
        or case_record.get("module_summary")
        or content
    )
    return {
        **case_record,
        **user_input,
        "basic_info": basic_info,
        "change_request": {
            "reason": change_reason,
            "current_design": user_input.get("current_design") or "",
            "change_proposal": change_description,
            "remarks": user_input.get("remarks") or "",
        },
        "change_reason": change_reason,
        "reason": change_reason,
        "current_design": user_input.get("current_design") or "",
        "change_proposal": change_description,
        "remarks": user_input.get("remarks") or "",
        "now": user_input.get("current_design") or "",
        "after": change_description,
        "implementation_plan": content or change_description,
        "revision_description": content or change_description,
    }


def _rag_results_for_history(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return [
        {
            "case_id": record.get("case_id") or record.get("case_no") or record.get("id"),
            "source_file": record.get("source_file") or record.get("pdf_file"),
            "matched_fields": record.get("matched_keywords")
            or record.get("matched_fields")
            or [],
            "similarity_score": record.get("similarity_score") or record.get("score"),
            "module_summary": record.get("module_summary")
            or record.get("search_text_preview")
            or record.get("reason_for_change")
            or "",
        }
        for record in records
    ]


def _module_prompt_for_history(module_id: str, template_file: str | None) -> str:
    template_note = (
        f"templates_pre/{template_file}"
        if template_file
        else "the editable Change Request description form"
    )
    return (
        "AI prompt: use the submitted keywords and retrieved historical PDF "
        f"evidence to complete {template_note}. Keep unsupported fields for "
        "human review."
    )


def modules_from_pdf_case_record(
    case_record: Dict[str, Any],
    user_input: Dict[str, Any] | None = None,
    *,
    rag_records: list[Dict[str, Any]] | None = None,
) -> list[Dict[str, Any]]:
    rag_results = _rag_results_for_history(rag_records or [case_record])
    modules: list[Dict[str, Any]] = []
    for module_id, meta in MODULE_TEMPLATE_MAP.items():
        template_file = meta["template_file"]
        source_content = str(
            case_record.get("search_text_preview")
            or case_record.get("module_summary")
            or case_record.get("reason_for_change")
            or ""
        )
        if module_id == "change-description":
            content = source_content
            exposed_template_file = None
        else:
            content = render_template_file(
                template_file,
                _template_context_for_history(
                    user_input,
                    content=source_content,
                    case_record=case_record,
                ),
            )
            exposed_template_file = template_file
        source_case = str(case_record.get("case_id") or case_record.get("case_no") or "")
        source_file = str(case_record.get("source_file") or case_record.get("pdf_file") or "")
        modules.append(
            {
                "id": module_id,
                "module_id": module_id,
                "title": meta["title"],
                "subtitle": template_file,
                "summary": _strip_html(content)[:240] if content else meta["title"],
                "description": _strip_html(content)[:240] if content else "",
                "content_md": content,
                "source_cases": [source_case] if source_case else [],
                "source_files": [source_file] if source_file else [],
                "needs_human_input": not bool(content),
                "warnings": []
                if content
                else ["No template content was generated for this module."],
                "data": {
                    "source_file": source_file,
                    "content": content,
                    "template_file": exposed_template_file,
                    "rag_retrieval_results": rag_results,
                    "ai_prompt": _module_prompt_for_history(
                        module_id,
                        exposed_template_file,
                    ),
                },
            }
        )
    return modules


def modules_from_historical_case(
    historical_case,
    user_input: Dict[str, Any] | None = None,
) -> list[Dict[str, Any]]:
    case_record = case_to_list_item(historical_case)
    source_by_editable_id = {
        "change-description": "basic_information",
        "impact-analysis": "change_description",
        "validation-plan": "reason_for_change",
        "validation-result": "impact_analysis",
        "implementation-plan": "implementation_plan",
        "implementation-result": "approval_signoff_information",
    }
    rag_record = {
        **case_record,
        "case_id": historical_case.case_id,
        "source_file": historical_case.source_file,
        "module_summary": case_record.get("module_summary", ""),
    }
    modules: list[Dict[str, Any]] = []
    for module_id, meta in MODULE_TEMPLATE_MAP.items():
        template_file = meta["template_file"]
        source_key = source_by_editable_id[module_id]
        source_module = next(
            (
                module
                for key, module in historical_case.modules.items()
                if str(getattr(key, "value", key)) == source_key
            ),
            None,
        )
        source_content = str(
            getattr(source_module, "content", "")
            or getattr(source_module, "summary", "")
            or ""
        )
        if module_id == "change-description":
            content = source_content
            exposed_template_file = None
        else:
            content = render_template_file(
                template_file,
                _template_context_for_history(
                    user_input,
                    content=source_content,
                    case_record=case_record,
                ),
            )
            exposed_template_file = template_file
        modules.append(
            {
                "id": module_id,
                "module_id": module_id,
                "title": meta["title"],
                "subtitle": template_file,
                "summary": _strip_html(content)[:240] if content else meta["title"],
                "description": _strip_html(content)[:240] if content else "",
                "content_md": content,
                "source_cases": [historical_case.case_id],
                "source_files": [historical_case.source_file],
                "needs_human_input": not bool(content),
                "warnings": []
                if content
                else ["No extracted content for this module."],
                "data": {
                    "source_file": historical_case.source_file,
                    "content": content,
                    "template_file": exposed_template_file,
                    "rag_retrieval_results": _rag_results_for_history([rag_record]),
                    "ai_prompt": _module_prompt_for_history(
                        module_id,
                        exposed_template_file,
                    ),
                },
            }
        )
    return modules


@router.get("/module-drafts")
def get_pd_ecr_module_draft(
    record_id: str,
    module_id: str,
):
    with get_draft_db_connection() as connection:
        draft = connection.execute(
            """
            SELECT record_id, module_id, data, title, created_at, updated_at
            FROM pd_ecr_module_draft
            WHERE record_id = ? AND module_id = ?
            """,
            (record_id, module_id),
        ).fetchone()

    if not draft:
        return {"record_id": record_id, "module_id": module_id, "data": None}

    return {
        "record_id": draft["record_id"],
        "module_id": draft["module_id"],
        "title": draft["title"],
        "data": _parse_draft_data(draft["data"]),
        "created_at": draft["created_at"],
        "updated_at": draft["updated_at"],
    }


@router.post("/module-drafts")
def save_pd_ecr_module_draft(
    payload: PdEcrModuleDraftPayload,
):
    record_id = payload.record_id.strip()
    module_id = payload.module_id.strip()

    if not record_id or not module_id:
        raise HTTPException(
            status_code=400,
            detail="record_id and module_id are required",
        )

    data_json = json.dumps(payload.data, ensure_ascii=False)

    with get_draft_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO pd_ecr_module_draft (record_id, module_id, data, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(record_id, module_id)
            DO UPDATE SET
                data = excluded.data,
                title = excluded.title,
                updated_at = CURRENT_TIMESTAMP
            """,
            (record_id, module_id, data_json, payload.title),
        )
        connection.commit()
        draft = connection.execute(
            """
            SELECT record_id, module_id, data, title, created_at, updated_at
            FROM pd_ecr_module_draft
            WHERE record_id = ? AND module_id = ?
            """,
            (record_id, module_id),
        ).fetchone()

    return {
        "record_id": draft["record_id"],
        "module_id": draft["module_id"],
        "title": draft["title"],
        "data": json.loads(draft["data"]),
        "created_at": draft["created_at"],
        "updated_at": draft["updated_at"],
    }


@router.get("/module-drafts/list")
def list_pd_ecr_module_drafts(
    record_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    with get_draft_db_connection() as connection:
        if record_id:
            rows = connection.execute(
                """
                SELECT record_id, module_id, data, title, created_at, updated_at
                FROM pd_ecr_module_draft
                WHERE record_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (record_id, limit, offset),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT record_id, module_id, data, title, created_at, updated_at
                FROM pd_ecr_module_draft
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

    return {
        "drafts": [
            {
                "record_id": row["record_id"],
                "module_id": row["module_id"],
                "title": row["title"],
                "data": _parse_draft_data(row["data"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ],
    }


@router.delete("/module-drafts")
def delete_pd_ecr_module_draft(
    record_id: str,
    module_id: str,
):
    if not record_id or not module_id:
        raise HTTPException(
            status_code=400,
            detail="record_id and module_id are required",
        )

    with get_draft_db_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM pd_ecr_module_draft
            WHERE record_id = ? AND module_id = ?
            """,
            (record_id, module_id),
        )
        connection.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {"deleted": True, "record_id": record_id, "module_id": module_id}


@router.post("/cases")
def create_pd_ecr_case(
    payload: PdEcrCaseCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = create_case(session=session, case_in=payload, current_user=current_user)
    return {
        "case": serialize_case(case),
        "modules": [
            serialize_module(module)
            for module in list_modules(session=session, case_id=case.id)
        ],
    }


@router.post("/cases/generate-from-ai")
def create_pd_ecr_case_from_ai(
    payload: PdEcrGenerateCasePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        return create_case_from_ai(
            session=session,
            input_data=payload.input,
            similar_cases=payload.similar_cases,
            current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"PD-ECR AI case creation failed: {e}",
        )


@router.patch("/cases/{case_id}")
def update_pd_ecr_case(
    case_id: str,
    payload: PdEcrCaseUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    return {
        "case": serialize_case(
            update_case(
                session=session,
                case=case,
                case_in=payload,
                current_user=current_user,
            )
        )
    }


@router.post("/cases/{case_id}/transition")
def transition_pd_ecr_case(
    case_id: str,
    payload: PdEcrTransitionPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    return {
        "case": serialize_case(
            transition_case(
                session=session,
                case=case,
                next_status=payload.status,
                current_user=current_user,
            )
        )
    }


@router.post("/cases/{case_id}/workflow/submit")
def submit_pd_ecr_workflow(
    case_id: str,
    payload: PdEcrWorkflowSubmitPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    return submit_for_department_confirmation(
        session=session,
        case=case,
        selected_departments=payload.selected_departments,
        assignees=payload.assignees,
        current_user=current_user,
    )


@router.post("/cases/{case_id}/workflow/publish-departments")
def publish_pd_ecr_departments(
    case_id: str,
    payload: PdEcrPublishDepartmentsPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    return publish_case_to_departments(
        session=session,
        case=case,
        selected_departments=payload.selected_departments,
        current_user=current_user,
    )


@router.post("/cases/{case_id}/workflow/assign-execution")
def assign_pd_ecr_execution(
    case_id: str,
    payload: PdEcrAssignExecutionPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    return assign_execution_tasks(
        session=session,
        case=case,
        assignments=[item.model_dump(mode="json") for item in payload.assignments],
        current_user=current_user,
    )


@router.get("/cases/{case_id}/workflow")
def get_pd_ecr_workflow(case_id: str, session: SessionDep):
    case = get_case_or_404(session=session, case_id=case_id)
    return get_workflow_state(session=session, case=case)


@router.post("/workflow/execution-tasks/{task_id}/confirm-assignment")
def confirm_pd_ecr_execution_assignment(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
):
    return confirm_execution_assignment(
        session=session,
        task_id=task_id,
        current_user=current_user,
    )


@router.post("/workflow/execution-tasks/{task_id}/complete")
def complete_pd_ecr_execution_task(
    task_id: uuid.UUID,
    payload: PdEcrExecutionCompletePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return complete_execution_task(
        session=session,
        task_id=task_id,
        execution_result=payload.execution_result,
        execution_note=payload.execution_note,
        evidence_note=payload.evidence_note,
        current_user=current_user,
    )


@router.post("/workflow/execution-tasks/{task_id}/request-changes")
def request_pd_ecr_execution_changes(
    task_id: uuid.UUID,
    payload: PdEcrWorkflowCommentPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return request_execution_task_changes(
        session=session,
        task_id=task_id,
        comment=payload.comment,
        current_user=current_user,
    )


@router.post("/workflow/department-tasks/{task_id}/confirm")
def confirm_pd_ecr_department_task(
    task_id: uuid.UUID,
    payload: PdEcrDepartmentTaskConfirmPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return confirm_department_task(
        session=session,
        task_id=task_id,
        impact_result=payload.impact_result,
        impact_remark=payload.impact_remark,
        action_required=payload.action_required,
        current_user=current_user,
    )


@router.post("/workflow/department-tasks/{task_id}/request-changes")
def request_pd_ecr_department_changes(
    task_id: uuid.UUID,
    payload: PdEcrWorkflowCommentPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return request_department_changes(
        session=session,
        task_id=task_id,
        comment=payload.comment,
        current_user=current_user,
    )


@router.post("/workflow/leader-tasks/{task_id}/review")
def review_pd_ecr_leader_task(
    task_id: uuid.UUID,
    payload: PdEcrLeaderReviewPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return review_leader_task(
        session=session,
        task_id=task_id,
        decision=payload.decision,
        review_comment=payload.review_comment,
        signature_name=payload.signature_name,
        current_user=current_user,
    )


@router.get("/cases/{case_id}/modules")
def list_pd_ecr_case_modules_v1(case_id: str, session: SessionDep):
    case = get_case_or_404(session=session, case_id=case_id)
    return {
        "case": serialize_case(case),
        "modules": [
            serialize_module(module)
            for module in list_modules(session=session, case_id=case.id)
        ],
    }


@router.patch("/cases/{case_id}/modules/{module_id}")
def update_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrModuleUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    module = update_module(
        session=session,
        case=case,
        module_id=module_id,
        module_in=payload,
        current_user=current_user,
    )
    return {"module": serialize_module(module)}


@router.patch("/cases/{case_id}/modules/{module_id}/assignment")
def assign_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrModuleAssignmentPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    module = assign_module(
        session=session,
        case=case,
        module_id=module_id,
        assignee_id=payload.assignee_id,
        assignee_email=payload.assignee_email,
        assignee_name=payload.assignee_name,
        department=payload.department,
        due_date=payload.due_date,
        reminder_policy=payload.reminder_policy,
        current_user=current_user,
    )
    notification = None
    if payload.send_assignment_email and module.reminder_policy.get(
        "on_assignment", True
    ):
        notification = send_module_assignment_email(
            session=session,
            case=case,
            module=module,
        )
    return {
        "module": serialize_module(module),
        "notification": notification.model_dump(mode="json") if notification else None,
    }


@router.post("/cases/{case_id}/modules/{module_id}/send-reminder")
def send_pd_ecr_module_reminder(
    case_id: str,
    module_id: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    ensure_case_manage_access(case, current_user)
    module = next(
        (
            item
            for item in list_modules(session=session, case_id=case.id)
            if item.module_id == module_id
        ),
        None,
    )
    if module is None:
        raise HTTPException(status_code=404, detail="PD-ECR module not found")
    notification = send_module_assignment_email(
        session=session,
        case=case,
        module=module,
    )
    return {"notification": notification.model_dump(mode="json")}


@router.post("/notifications/run-due-reminders")
def run_pd_ecr_due_reminders(
    session: SessionDep,
    current_user: CurrentUser,
):
    if (
        not current_user.is_superuser
        and getattr(current_user, "pd_ecr_role", None) != "pd_ecr_manager"
    ):
        raise HTTPException(status_code=403, detail="No permission to run reminders")
    return run_due_reminders(session=session)


@router.post("/cases/{case_id}/modules/{module_id}/regenerate")
def regenerate_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrRegenerateModulePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return regenerate_module_preview(
        session=session,
        case_id=case_id,
        module_id=module_id,
        instruction=payload.instruction,
        current_user=current_user,
    )


@router.post("/cases/{case_id}/modules/{module_id}/apply-generated")
def apply_generated_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrApplyGeneratedModulePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return apply_generated_module(
        session=session,
        case_id=case_id,
        module_id=module_id,
        generated=payload.generated,
        expected_version=payload.expected_version,
        current_user=current_user,
    )


@router.get("/cases/{case_id}/versions")
def list_pd_ecr_case_versions(case_id: str, session: SessionDep):
    case = get_case_or_404(session=session, case_id=case_id)
    versions = session.exec(
        select(PdEcrVersion)
        .where(PdEcrVersion.case_id == case.id)
        .order_by(PdEcrVersion.created_at.desc())
    ).all()
    return {
        "case_id": str(case.id),
        "versions": [
            {
                "id": str(version.id),
                "entity_type": version.entity_type,
                "entity_id": version.entity_id,
                "version": version.version,
                "snapshot": version.snapshot,
                "diff_metadata": version.diff_metadata,
                "created_by_id": str(version.created_by_id)
                if version.created_by_id
                else None,
                "created_at": version.created_at.isoformat()
                if version.created_at
                else None,
            }
            for version in versions
        ],
    }


@router.get("/cases/{case_id}/activity")
def list_pd_ecr_case_activity(case_id: str, session: SessionDep):
    case = get_case_or_404(session=session, case_id=case_id)
    activities = session.exec(
        select(PdEcrActivity)
        .where(PdEcrActivity.case_id == case.id)
        .order_by(PdEcrActivity.created_at.desc())
    ).all()
    return {
        "case_id": str(case.id),
        "activities": [
            {
                "id": str(activity.id),
                "action": activity.action,
                "target_type": activity.target_type,
                "target_id": activity.target_id,
                "message": activity.message,
                "metadata": activity.metadata_json,
                "actor_id": str(activity.actor_id) if activity.actor_id else None,
                "created_at": activity.created_at.isoformat()
                if activity.created_at
                else None,
            }
            for activity in activities
        ],
    }


@router.post("/cases/{case_id}/tasks")
def create_pd_ecr_case_task(
    case_id: str,
    payload: PdEcrTaskCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    task = create_task(
        session=session,
        case=case,
        task_in=payload,
        current_user=current_user,
    )
    return {
        "task": {
            "id": str(task.id),
            "case_id": str(task.case_id),
            "module_id": task.module_id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "assignee_id": str(task.assignee_id) if task.assignee_id else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        }
    }


@router.post("/cases/{case_id}/comments")
def create_pd_ecr_case_comment(
    case_id: str,
    payload: PdEcrCommentCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    comment = create_comment(
        session=session,
        case=case,
        comment_in=payload,
        current_user=current_user,
    )
    return {
        "comment": {
            "id": str(comment.id),
            "case_id": str(comment.case_id),
            "target_type": comment.target_type,
            "target_id": comment.target_id,
            "body": comment.body,
            "author_id": str(comment.author_id) if comment.author_id else None,
            "created_at": comment.created_at.isoformat()
            if comment.created_at
            else None,
        }
    }


@router.post("/cases/upload-file")
async def upload_pd_ecr_case_file(
    file: UploadFile,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Upload a single Excel or PDF file to create a PD-ECR case.

    Returns parsed metadata, case info, and content preview.
    The file is automatically added to the FAISS knowledge index in the background.
    """
    import threading
    from app.core.config import settings

    # Validate file type
    filename = file.filename or "unknown"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ("xlsx", "xlsm", "xls", "pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{suffix}. Supported: .xlsx, .xls, .pdf",
        )

    # Save uploaded file to uploads directory
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = upload_dir / safe_name

    try:
        content = await file.read()
        file_path.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    # Parse and ingest (sync, but ok for typical file sizes)
    try:
        result = ingest_uploaded_file(
            session=session,
            file_path=file_path,
            original_filename=filename,
            current_user=current_user,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process file: {exc}")

    # Trigger background FAISS index rebuild
    def _rebuild():
        try:
            from app.rag.build_index import rebuild_index
            rebuild_index()
        except Exception:
            traceback.print_exc()

    threading.Thread(target=_rebuild, daemon=True).start()

    return {
        "status": "ok",
        "filename": filename,
        "indexing": {
            "pending": True,
            "message": "文件已入库，知识库正在后台索引中。新数据将在数秒后可供检索。",
        },
        **result,
    }


def _file_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "updated_at": (
            datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            if path.exists()
            else None
        ),
    }


@router.get("/knowledge-base/status")
def get_knowledge_base_status(session: SessionDep):
    """Return the RAG knowledge base indexing status.

    Users can call this to verify their uploaded files have been indexed.
    """
    import shutil

    from app.rag.build_index import (
        INDEX_PATH,
        META_PATH,
        VECTOR_DIR,
        get_rebuild_status,
    )

    rebuild = get_rebuild_status()

    # Count files currently in the knowledge directory
    knowledge_dir = Path(__file__).resolve().parents[2] / "rag" / "knowledge"
    file_count = 0
    if knowledge_dir.exists():
        file_count = len([
            p for p in knowledge_dir.rglob("*")
            if p.suffix.lower() in (".md", ".txt") and "_signature_structured" not in p.stem
        ])

    staged_docs = session.exec(select(PdEcrStagedDocument)).all()
    staged_counts = {
        "pending": 0,
        "confirmed": 0,
        "rejected": 0,
        "total": len(staged_docs),
    }
    for doc in staged_docs:
        status = doc.status or "pending"
        staged_counts[status] = staged_counts.get(status, 0) + 1

    index_status = _file_status(INDEX_PATH)
    meta_status = _file_status(META_PATH)
    chunk_files = len(list(VECTOR_DIR.glob("chunks_*.pkl"))) if VECTOR_DIR.exists() else 0

    return {
        "knowledge_files_on_disk": file_count,
        "knowledge_dir": str(knowledge_dir),
        "vector_store": {
            "index_path": str(INDEX_PATH),
            "meta_path": str(META_PATH),
            "index_exists": index_status["exists"],
            "meta_exists": meta_status["exists"],
            "index_size_bytes": index_status["size_bytes"],
            "meta_size_bytes": meta_status["size_bytes"],
            "index_updated_at": index_status["updated_at"],
            "meta_updated_at": meta_status["updated_at"],
            "chunk_files": chunk_files,
        },
        "staged_documents": staged_counts,
        "parser_capabilities": {
            "xlsx_controls": True,
            "excel_to_markdown": True,
            "pdf_to_markdown": True,
            "mineru": shutil.which("mineru") is not None,
            "libreoffice": bool(shutil.which("libreoffice") or shutil.which("soffice")),
        },
        "last_rebuild": rebuild,
    }


# ══════════════════════════════════════════════════════════════════════════
# Staged Document Review Flow
# upload → parse → stage → review → edit → confirm → case + knowledge base
# ══════════════════════════════════════════════════════════════════════════

class PdEcrStagedDocumentResponse(BaseModel):
    id: str
    status: str
    original_filename: str
    file_type: str
    preview_pdf_url: str | None = None
    parsed_text: str = ""
    metadata: dict[str, Any] = {}
    sections: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    created_at: str | None = None
    updated_at: str | None = None


def _staged_to_response(doc: PdEcrStagedDocument) -> PdEcrStagedDocumentResponse:
    return PdEcrStagedDocumentResponse(
        id=str(doc.id),
        status=doc.status,
        original_filename=doc.original_filename,
        file_type=doc.file_type,
        preview_pdf_url=(
            f"/api/v1/pd-ecr/documents/{doc.id}/preview"
            if doc.preview_pdf_path
            else None
        ),
        parsed_text=doc.parsed_text,
        metadata=doc.metadata_json,
        sections=doc.sections_json,
        tables=doc.tables_json,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
    )


@router.post(
    "/documents/upload",
    response_model=PdEcrStagedDocumentResponse,
)
async def upload_and_stage_document(
    file: UploadFile,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Upload a file, parse it, and create a staged document for review.

    The parsed result is NOT written to the case database yet.
    User must review and call POST /documents/{id}/confirm to commit.
    """
    from app.core.config import settings
    from app.services.pd_ecr_stage_service import stage_uploaded_file

    filename = file.filename or "unknown"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ("xlsx", "xlsm", "xls", "pdf", "docx", "doc"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{suffix}. Supported: .xlsx, .xls, .pdf, .docx",
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = upload_dir / safe_name

    try:
        content = await file.read()
        file_path.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    try:
        staged = stage_uploaded_file(
            session=session,
            file_path=file_path,
            original_filename=filename,
            user=current_user,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {exc}")

    return _staged_to_response(staged)


@router.get(
    "/documents/{doc_id}",
    response_model=PdEcrStagedDocumentResponse,
)
def get_staged_document(
    doc_id: str,
    session: SessionDep,
):
    """Retrieve a staged document for review."""
    from app.services.pd_ecr_stage_service import get_staged_document

    doc = get_staged_document(session=session, doc_id=doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Staged document not found")
    return _staged_to_response(doc)


@router.patch(
    "/documents/{doc_id}",
    response_model=PdEcrStagedDocumentResponse,
)
def update_staged_document(
    doc_id: str,
    payload: PdEcrStagedDocumentUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Save user edits to a staged document's metadata, sections, or tables."""
    from app.services.pd_ecr_stage_service import get_staged_document, update_staged_document

    doc = get_staged_document(session=session, doc_id=doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Staged document not found")
    if doc.status != "pending":
        raise HTTPException(status_code=400, detail="Document is already confirmed or rejected")

    updated = update_staged_document(session=session, doc=doc, payload=payload)
    return _staged_to_response(updated)


@router.post("/documents/{doc_id}/confirm")
def confirm_staged_document(
    doc_id: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Confirm a staged document: create PdEcrCase + modules + vector chunks + FAISS rebuild."""
    from app.services.pd_ecr_stage_service import get_staged_document, confirm_staged_document

    doc = get_staged_document(session=session, doc_id=doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Staged document not found")
    if doc.status == "confirmed":
        raise HTTPException(status_code=400, detail="Document is already confirmed")

    result = confirm_staged_document(session=session, doc=doc, user=current_user)
    return result


@router.get("/documents/{doc_id}/preview")
def get_staged_document_preview(doc_id: str, session: SessionDep):
    """Serve the preview PDF for a staged document."""
    from app.services.pd_ecr_stage_service import get_staged_document

    doc = get_staged_document(session=session, doc_id=doc_id)
    if doc is None or not doc.preview_pdf_path:
        raise HTTPException(status_code=404, detail="Preview not available")

    pdf_path = Path(doc.preview_pdf_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Preview file not found on disk")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=doc.original_filename.rsplit(".", 1)[0] + ".pdf",
        content_disposition_type="inline",
    )


@router.post("/import/historical")
def import_pd_ecr_historical_cases(
    payload: PdEcrImportPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Only admins can import historical cases"
        )
    return import_historical_sources(
        session=session,
        current_user=current_user,
        limit=payload.limit,
    )


@router.post("/requests")
def create_pd_ecr_v1_request(payload: Dict[str, Any]):
    try:
        request = NewPdEcrRequest.from_legacy_input(payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid PD-ECR request: {e}")

    request_json = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    request_id = "req-" + hashlib.sha256(request_json.encode("utf-8")).hexdigest()[:16]
    return {
        "request_id": request_id,
        "input": request.model_dump(mode="json"),
        "missing_fields": [],
    }


@router.post("/retrieve")
def retrieve_pd_ecr_similar_cases(payload: PdEcrRetrievePayload):
    user_input = payload.input or {}
    top_k = max(1, min(payload.top_k or 5, 20))
    try:
        request, results = retrieve_similar_cases(
            user_input,
            top_k=top_k,
            filters=payload.filters,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PD-ECR retrieval failed: {e}")

    return {
        "query_input": request.model_dump(mode="json"),
        "top_k": top_k,
        "results": [result.model_dump(mode="json") for result in results[:top_k]],
    }


class PdEcrInput(BaseModel):
    dc_no: str = ""
    date: str = ""
    customer_project: str = ""
    mcr_no: str = ""
    product_no: str = ""
    part_no: str = ""
    component_no: str = ""
    change_type: str = ""
    initiator: str = ""
    reason: str = ""
    current_design: str = ""
    change_proposal: str = ""
    remarks: str = ""


def get_llm_client() -> AsyncOpenAI:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")

    if not api_key:
        raise RuntimeError("缺少 LLM_API_KEY，请在 .env 中配置")

    if base_url:
        return AsyncOpenAI(api_key=api_key, base_url=base_url)

    return AsyncOpenAI(api_key=api_key)


def clean_json_text(content: str) -> str:
    if not content:
        return ""

    content = content.strip()

    if content.startswith("```json"):
        content = content.replace("```json", "", 1).strip()

    if content.startswith("```"):
        content = content.replace("```", "", 1).strip()

    if content.endswith("```"):
        content = content[:-3].strip()

    return content


def safe_filename(text: str) -> str:
    if not text:
        return "unknown"

    text = str(text).strip()

    # 把 Windows 不允许的文件名字符替换成 _
    text = re.sub(r'[\\/:*?"<>|\t\r\n]+', "_", text)

    # 把多个空格压缩成一个 _
    text = re.sub(r"\s+", "_", text)

    # 防止文件名太长
    text = text[:80]

    return text or "unknown"


def normalize_impact_check_from_rag(
    result: Dict[str, Any], rag_context: str
) -> Dict[str, Any]:
    """
    从历史 RAG 文本中抽取 Step 3 Impact Yes/No Check。
    如果历史表格里有明确 Yes/No，则覆盖 LLM 的判断。
    """

    if not isinstance(result, dict) or not rag_context:
        return result

    item_map = {
        "function": {
            "value_key": "function_performance_value",
            "confirmed_key": "function_performance_confirmed_by",
            "keywords": ["function", "performance", "产品功能", "性能"],
        },
        "interface": {
            "value_key": "interface_appearance_value",
            "confirmed_key": "interface_appearance_confirmed_by",
            "keywords": ["interface", "appearance", "接口", "外观"],
        },
        "reliability": {
            "value_key": "reliability_robustness_value",
            "confirmed_key": "reliability_robustness_confirmed_by",
            "keywords": ["reliability", "robustness", "可靠性", "鲁棒性"],
        },
        "other_components": {
            "value_key": "other_components_value",
            "confirmed_key": "other_components_confirmed_by",
            "keywords": ["other components", "其他零部件"],
        },
        "manufacturing": {
            "value_key": "manufacturing_assembly_testing_value",
            "confirmed_key": "manufacturing_assembly_testing_confirmed_by",
            "keywords": [
                "manufacturing",
                "assembly",
                "testing",
                "加工",
                "装配",
                "测试",
            ],
        },
        "supplier": {
            "value_key": "supplier_part_value",
            "confirmed_key": "supplier_part_confirmed_by",
            "keywords": ["supplier", "供应商"],
        },
        "system": {
            "value_key": "system_hw_sw_calibration_mechanical_value",
            "confirmed_key": "system_hw_sw_calibration_mechanical_confirmed_by",
            "keywords": [
                "system",
                "hardware",
                "software",
                "calibration",
                "mechanical",
                "系统",
                "硬件",
                "软件",
            ],
        },
    }

    def parse_yes_no_from_line(line: str):
        # Markdown 表格优先
        if "|" in line:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            text = " ".join(cells)

            # 常见列顺序：No | Check Item | No | Yes | Confirmed by
            # 如果同时有 ☑ 和 ☐，根据位置判断
            if len(cells) >= 5:
                no_cell = cells[-3]
                yes_cell = cells[-2]
                confirmed = cells[-1]

                if "☑" in yes_cell or "√" in yes_cell or "✓" in yes_cell:
                    return "yes", confirmed

                if "☑" in no_cell or "√" in no_cell or "✓" in no_cell:
                    return "no", confirmed

            return "", ""

        return "", ""

    for line in str(rag_context).splitlines():
        low = line.lower()

        for _, cfg in item_map.items():
            if not any(k.lower() in low or k in line for k in cfg["keywords"]):
                continue

            value, confirmed_by = parse_yes_no_from_line(line)

            if value in ["yes", "no"]:
                result[cfg["value_key"]] = value

            if confirmed_by:
                result[cfg["confirmed_key"]] = confirmed_by
                result[f"{cfg['confirmed_key']}_source"] = "根据历史案例推荐"

    return result


def normalize_affected_documents_from_rag(
    result: Dict[str, Any], rag_context: str
) -> Dict[str, Any]:
    """
    从 RAG 历史文本中强制抽取 Step 3.3 Affected Documents Check。
    如果历史报告里明确勾选 No / Yes，则覆盖 LLM 推理结果。
    """

    if not isinstance(result, dict):
        return result

    if not rag_context:
        return result

    doc_items = [
        {
            "name": "interface_fmea",
            "value_key": "interface_fmea_value",
            "resp_key": "interface_fmea_resp_person",
            "due_key": "interface_fmea_due_date",
            "source_key": "interface_fmea_resp_source",
            "keywords": [
                "interface fmea",
                "ifmea",
                "interface-fmea",
                "接口 fmea",
                "接口失效",
                "ifmea",
            ],
        },
        {
            "name": "product_fmea",
            "value_key": "product_fmea_value",
            "resp_key": "product_fmea_resp_person",
            "due_key": "product_fmea_due_date",
            "source_key": "product_fmea_resp_source",
            "keywords": ["product fmea", "dfmea", "d fmea", "产品 fmea", "设计 fmea"],
        },
        {
            "name": "special_characteristics",
            "value_key": "special_characteristics_value",
            "resp_key": "special_characteristics_resp_person",
            "due_key": "special_characteristics_due_date",
            "source_key": "special_characteristics_resp_source",
            "keywords": ["special characteristics", "psc", "特殊特性", "特殊特征"],
        },
        {
            "name": "imds",
            "value_key": "imds_value",
            "resp_key": "imds_resp_person",
            "due_key": "imds_due_date",
            "source_key": "imds_resp_source",
            "keywords": ["imds", "material data", "材料数据"],
        },
        {
            "name": "offer_drawing",
            "value_key": "offer_drawing_value",
            "resp_key": "offer_drawing_resp_person",
            "due_key": "offer_drawing_due_date",
            "source_key": "offer_drawing_resp_source",
            "keywords": [
                "offer drawing",
                "offer-drawing",
                "customer drawing",
                "报价图",
                "客户图纸",
            ],
        },
        {
            "name": "tcd",
            "value_key": "tcd_value",
            "resp_key": "tcd_resp_person",
            "due_key": "tcd_due_date",
            "source_key": "tcd_resp_source",
            "keywords": ["tcd", "technical customer documentation", "技术客户文件"],
        },
        {
            "name": "norm_wb_hf",
            "value_key": "norm_wb_hf_value",
            "resp_key": "norm_wb_hf_resp_person",
            "due_key": "norm_wb_hf_due_date",
            "source_key": "norm_wb_hf_resp_source",
            "keywords": ["norm", "wb", "hf", "norm, wb, hf", "标准", "规范"],
        },
        {
            "name": "affected_document_other",
            "value_key": "affected_document_other_value",
            "resp_key": "affected_document_other_resp_person",
            "due_key": "affected_document_other_due_date",
            "source_key": "affected_document_other_resp_source",
            "keywords": [
                "wi check",
                "wi",
                "work instruction",
                "other",
                "其他",
                "作业指导书",
            ],
        },
    ]

    def has_checked_mark(text: str) -> bool:
        text = str(text or "").strip()
        return any(
            mark in text for mark in ["☑", "☒", "√", "✓", "[x]", "[X]", "checked"]
        )

    def split_markdown_cells(line: str) -> list[str]:
        return [c.strip() for c in str(line).split("|") if c.strip()]

    def normalize_line(line: str) -> str:
        return str(line or "").lower().replace("_", " ").replace("-", " ")

    def match_doc_item(line: str):
        low = normalize_line(line)
        for item in doc_items:
            for kw in item["keywords"]:
                if kw.lower() in low:
                    return item
        return None

    def parse_date_from_text(text: str) -> str:
        text = str(text or "")
        m = re.search(r"\b(20\d{2}[-/.]?\d{2}[-/.]?\d{2})\b", text)
        if not m:
            return ""
        return normalize_date_string(m.group(1).replace("/", "-").replace(".", "-"))

    for raw_line in str(rag_context).splitlines():
        line = str(raw_line or "").strip()

        if not line:
            continue

        low = line.lower()

        # 跳过表头和分隔行
        if "document item" in low or "文档项" in line:
            continue

        if set(line.replace("|", "").replace("-", "").replace(" ", "")) == set():
            continue

        item = match_doc_item(line)
        if not item:
            continue

        value = ""
        responsible = ""
        due_date = ""

        # Markdown 表格格式：
        # | 1 | Interface FMEA relevant / IFMEA | ☑ | ☐ | xxx | 2026-xx-xx |
        if "|" in line:
            cells = split_markdown_cells(line)

            # 常见结构：No. | Document Item | No | Yes | Responsible | Due Date
            if len(cells) >= 4:
                no_cell = cells[2]
                yes_cell = cells[3]

                if has_checked_mark(no_cell):
                    value = "no"
                elif has_checked_mark(yes_cell):
                    value = "yes"

                if len(cells) >= 5:
                    responsible = cells[4].strip()

                if len(cells) >= 6:
                    due_date = parse_date_from_text(cells[5])

        else:
            # 非表格格式兜底：一行里根据 No/Yes 附近的勾选判断
            # 优先识别 “No ☑ Yes ☐”
            no_match = re.search(
                r"(no|否)\s*[:：]?\s*(☑|☒|√|✓|\[x\]|\[X\])", line, re.I
            )
            yes_match = re.search(
                r"(yes|是)\s*[:：]?\s*(☑|☒|√|✓|\[x\]|\[X\])", line, re.I
            )

            if no_match:
                value = "no"
            elif yes_match:
                value = "yes"

            due_date = parse_date_from_text(line)

        if value in ["yes", "no"]:
            result[item["value_key"]] = value
            result[item["source_key"]] = "根据历史案例推荐"

            # 如果历史是 no，一般不需要负责人和日期，避免模型乱填
            if value == "no":
                result[item["resp_key"]] = ""
                result[item["due_key"]] = ""
            else:
                if responsible:
                    result[item["resp_key"]] = responsible
                if due_date:
                    result[item["due_key"]] = due_date

    return result


def extract_case_code(name: str) -> str:
    """
    从文件名里提取 T0001 / T0002 / T0005 这类编号。
    """
    text = str(name or "")
    m = re.search(r"(T\d{4,})", text, re.I)
    if m:
        return m.group(1).upper()
    return ""


def normalize_stem_name(name: str) -> str:
    """
    归一化文件名，用于匹配：
    T0005-xxx.md
    T0005-xxx_signature_structured.md
    """
    stem = Path(str(name or "")).stem.strip()

    for suffix in [
        "_signature_structured",
        "_structured",
        "_signature",
    ]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]

    return stem.strip()


def get_best_source_document_from_results(results: list) -> str:
    """
    从主 RAG 检索结果里找最相似的原始历史文件。
    优先返回非 _signature_structured 的 md。
    """
    if not results:
        return ""

    names = []

    for item in results:
        metadata = item.get("metadata", {}) or {}

        name = (
            metadata.get("document_name")
            or metadata.get("source_file")
            or metadata.get("source")
            or metadata.get("_source")
            or item.get("source")
            or item.get("source_file")
            or item.get("document_name")
            or ""
        )

        name = str(name or "").strip()

        if name:
            names.append(name)

    debug_print("========== best source candidates ==========")
    for n in names:
        debug_print(n)

    # 优先原始 md
    for name in names:
        low = name.lower()
        if low.endswith(".md") and "_signature_structured" not in low:
            return name

    # 其次 xlsx
    for name in names:
        if name.lower().endswith(".xlsx"):
            return name

    # 再其次任意包含 T000x 的文件
    for name in names:
        if extract_case_code(name):
            return name

    return names[0] if names else ""


def find_structured_signature_md(source_document_name: str) -> str:
    """
    根据主 RAG 命中的原始历史文件，读取对应的 _signature_structured.md。
    因为你的 structured md 已经放在 knowledge 目录，所以直接从 knowledge 里找。
    """
    debug_print("========== find_structured_signature_md DEBUG ==========")
    debug_print("source_document_name:", source_document_name)
    debug_print("STRUCTURED_SIGNATURE_DIR:", STRUCTURED_SIGNATURE_DIR)
    debug_print("dir exists:", STRUCTURED_SIGNATURE_DIR.exists())

    if not STRUCTURED_SIGNATURE_DIR.exists():
        return ""

    candidates = list(STRUCTURED_SIGNATURE_DIR.glob("*_signature_structured.md"))

    debug_print("structured files count:", len(candidates))
    debug_print("structured files:", [p.name for p in candidates])

    if not source_document_name:
        debug_print("source_document_name 为空，无法匹配 structured md")
        return ""

    source_stem = normalize_stem_name(source_document_name)
    source_code = extract_case_code(source_document_name)

    debug_print("source_stem:", source_stem)
    debug_print("source_code:", source_code)

    # 1. 精确匹配
    exact_path = STRUCTURED_SIGNATURE_DIR / f"{source_stem}_signature_structured.md"

    if exact_path.exists():
        debug_print("命中 structured md 精确匹配:", exact_path.name)
        return exact_path.read_text(encoding="utf-8", errors="ignore")

    # 2. stem 完全匹配
    for path in candidates:
        candidate_stem = normalize_stem_name(path.name)

        if candidate_stem == source_stem:
            debug_print("命中 structured md stem 匹配:", path.name)
            return path.read_text(encoding="utf-8", errors="ignore")

    # 3. T000x 编号匹配，最适合你现在这种文件命名
    if source_code:
        same_code_files = [
            p for p in candidates if extract_case_code(p.name) == source_code
        ]

        if same_code_files:
            path = same_code_files[0]
            debug_print("命中 structured md case_code 匹配:", path.name)
            return path.read_text(encoding="utf-8", errors="ignore")

    # 4. 模糊匹配
    for path in candidates:
        candidate_stem = normalize_stem_name(path.name)

        if source_stem in candidate_stem or candidate_stem in source_stem:
            debug_print("命中 structured md 模糊匹配:", path.name)
            debug_print("source_stem:", source_stem)
            debug_print("candidate_stem:", candidate_stem)
            return path.read_text(encoding="utf-8", errors="ignore")

    debug_print("未找到对应 structured md")
    return ""


def extract_structured_actual_approval_from_rag(
    result: Dict[str, Any],
    rag_context: str,
) -> Dict[str, Any]:
    """
    只从 structured_fields_actual_approval 区块读取签字人。
    不读取 Signature Matrix candidates。
    """
    if not isinstance(result, dict) or not rag_context:
        return result

    approval_keys = [
        "approval_development_person",
        "approval_purchasing_person",
        "approval_mfe_person",
        "approval_cos_person",
        "approval_quality_person",
        "approval_cpjm_person",
        "approval_moex_person",
        "approval_log_person",
        "approval_other_person",
    ]

    def clean_value(v: str) -> str:
        v = str(v or "").strip()
        v = v.split("|")[0].strip()
        v = v.replace("____", "").replace("_______", "").strip()
        return v

    invalid_exact = {
        "不影响",
        "无",
        "无需",
        "不涉及",
        "没有",
        "否",
        "na",
        "n/a",
        "none",
        "null",
        "x",
        "-",
        "/",
        "development",
        "purchasing",
        "quality",
        "mfe",
        "tef",
        "cos",
        "cpjm",
        "moex",
        "log",
        "研发",
        "开发",
        "采购",
        "质量",
        "工艺",
        "样品",
        "客户项目",
        "生产",
        "物流",
        "工程师",
        "测试",
        "验证",
        "设计",
        "机加工",
        "装配测试",
    }

    invalid_contains = [
        "signature matrix",
        "candidates",
        "candidate",
        "responsible",
        "implementation",
        "approval_source_note",
        "structured_fields_signature_matrix_candidates",
        "structured_fields_step_6_1_responsible",
        "不影响",
        "工程师",
        "测试",
        "验证",
        "设计",
    ]

    def normalize_person_name(v: str) -> str:
        v = clean_value(v)

        # xiang liangshan -> XIANG Liangshan
        if re.fullmatch(r"[a-z]+\s+[a-z]+(?:\s+[a-z]+)?", v):
            parts = v.split()
            surname = parts[0].upper()
            given = " ".join(p.capitalize() for p in parts[1:])
            return f"{surname} {given}"

        # Xiang Liangshan -> XIANG Liangshan
        if re.fullmatch(r"[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", v):
            parts = v.split()
            surname = parts[0].upper()
            given = " ".join(p.capitalize() for p in parts[1:])
            return f"{surname} {given}"

        return v

    def is_valid_person(v: str) -> bool:
        v = clean_value(v)
        low = v.lower()

        if not v:
            return False

        if v in invalid_exact or low in invalid_exact:
            return False

        if any(x in low for x in invalid_contains):
            return False

        # XIANG Liangshan / TAO Jiong
        if re.fullmatch(r"[A-Z]{2,}\s+[A-Z][a-z]+", v):
            return True

        # Xiang Liangshan / Wang Xiaolong
        if re.fullmatch(r"[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", v):
            return True

        # xiang liangshan / tao jiong
        if re.fullmatch(r"[a-z]+\s+[a-z]+(?:\s+[a-z]+)?", v):
            return True

        # 中文姓名
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", v):
            return True

        return False

    m_block = re.search(
        r"##\s*structured_fields_actual_approval(.*?)(?=##\s*structured_fields_|$)",
        rag_context,
        re.S | re.I,
    )

    if not m_block:
        debug_print("structured md 中没有找到 structured_fields_actual_approval 区块")
        return result

    block = m_block.group(1)

    debug_print("========== structured actual approval block START ==========")
    debug_print(block)
    debug_print("========== structured actual approval block END ==========")

    for key in approval_keys:
        pattern = rf"^{re.escape(key)}\s*[:：]\s*(.*)$"
        m = re.search(pattern, block, re.MULTILINE | re.IGNORECASE)

        if not m:
            continue

        value = clean_value(m.group(1))

        if is_valid_person(value):
            result[key] = normalize_person_name(value)
        else:
            result[key] = ""

    return result


def normalize_affected_documents_from_structured_rag(
    result: Dict[str, Any],
    rag_context: str,
) -> Dict[str, Any]:
    """
    从 structured md 读取 Step 3.3 affected documents。
    """
    if not isinstance(result, dict) or not rag_context:
        return result

    key_list = [
        "interface_fmea_value",
        "product_fmea_value",
        "special_characteristics_value",
        "imds_value",
        "offer_drawing_value",
        "tcd_value",
        "norm_wb_hf_value",
        "affected_document_other_value",
    ]

    m_block = re.search(
        r"##\s*structured_fields_step_3_3_affected_documents(.*?)(?=##\s*structured_fields_|$)",
        rag_context,
        re.S | re.I,
    )

    if not m_block:
        return result

    block = m_block.group(1)

    for key in key_list:
        pattern = rf"^{re.escape(key)}\s*[:：]\s*(yes|no)\s*$"
        m = re.search(pattern, block, re.MULTILINE | re.IGNORECASE)

        if m:
            result[key] = m.group(1).lower()

    return result


# 加该函数，形成三路检索
def build_affected_documents_search_input(user_input: Dict[str, Any]) -> Dict[str, Any]:
    affected_documents_keywords = """
    Step 3.3 Affected Documents Check
    影响文档检查
    Document Item 文档项目
    Interface FMEA relevant IFMEA
    product FMEA relevant DFMEA
    Special Characteristics relevant PSC
    IMDS relevant
    Offer drawing relevant
    TCD relevant
    Norm WB HF relevant
    WI Check
    No Yes Responsible Due Date
    No / 否
    Yes / 是
    """
    return {
        **user_input,
        "affected_documents_search_keywords": affected_documents_keywords,
    }


def build_prompt(data: Dict[str, Any], rag_context: str = "") -> str:
    # print("====== RAG CONTEXT START ======")
    # print(rag_context)
    # print("====== RAG CONTEXT END ======")

    # prompt = build_prompt(data, rag_context)
    """
    PD-ECR report prompt builder.

    核心原则：
    1. 用户输入字段直接保留。
    2. 需要 AI 判断的 yes/no、Y/N、responsible、confirmed_by 字段不要写死默认值。
    3. 历史案例中有明确勾选和负责人时，优先复制历史案例。
    4. 历史案例没有具体负责人时，才用部门兜底。
    """

    output_schema = {
        "basic_info": {
            "dc_no": data.get("dc_no", ""),
            "date": data.get("date", ""),
            "customer_project": data.get("customer_project", ""),
            "mcr_no": data.get("mcr_no", ""),
            "product_no": data.get("product_no", ""),
            "component_no": data.get("component_no", ""),
            "initiator": data.get("initiator", ""),
        },
        "change_request": {
            "reason": data.get("reason", ""),
            "current_design": data.get("current_design", ""),
            "change_proposal": data.get("change_proposal", ""),
            "remarks": data.get("remarks", ""),
        },
        "engineering_analysis": "",
        "impact_analysis": "",
        "impact_description": "",
        "risk_analysis": "",
        "verification_plan": "",
        "implementation_plan": "",
        "affected_documents": "",
        "suggested_approvers": [],
        "function_performance_value": "",
        "function_performance_confirmed_by": "",
        "function_performance_confirmed_by_source": "",
        "function_performance_source_file": "",
        "function_performance_evidence": "",
        "function_performance_comment": "",
        "interface_appearance_value": "",
        "interface_appearance_confirmed_by": "",
        "interface_appearance_confirmed_by_source": "",
        "interface_appearance_source_file": "",
        "interface_appearance_evidence": "",
        "interface_appearance_comment": "",
        "reliability_robustness_value": "",
        "reliability_robustness_confirmed_by": "",
        "reliability_robustness_confirmed_by_source": "",
        "reliability_robustness_source_file": "",
        "reliability_robustness_evidence": "",
        "reliability_robustness_comment": "",
        "other_components_value": "",
        "other_components_confirmed_by": "",
        "other_components_confirmed_by_source": "",
        "other_components_source_file": "",
        "other_components_evidence": "",
        "parallel_components_description": "",
        "other_components_comment": "",
        "manufacturing_assembly_testing_value": "",
        "manufacturing_assembly_testing_confirmed_by": "",
        "manufacturing_assembly_testing_confirmed_by_source": "",
        "manufacturing_assembly_testing_source_file": "",
        "manufacturing_assembly_testing_evidence": "",
        "manufacturing_assembly_testing_comment": "",
        "supplier_part_value": "",
        "supplier_part_confirmed_by": "",
        "supplier_part_confirmed_by_source": "",
        "supplier_part_source_file": "",
        "supplier_part_evidence": "",
        "supplier_part_comment": "",
        "system_hw_sw_calibration_mechanical_value": "",
        "system_hw_sw_calibration_mechanical_confirmed_by": "",
        "system_hw_sw_calibration_mechanical_confirmed_by_source": "",
        "system_hw_sw_calibration_mechanical_source_file": "",
        "system_hw_sw_calibration_mechanical_evidence": "",
        "system_hw_sw_calibration_mechanical_description": "",
        "system_hw_sw_calibration_mechanical_comment": "",
        "cost_increase_box": "",
        "cost_decrease_box": "",
        "cost_no_change_box": "",
        "cost_impact_description": "",
        "mixed_deliveries_comment": "",
        "mixed_deliveries_value": "",
        "stock_delivery_treatment_answer": "",
        "stock_delivery_treatment_confirmed_by": "",
        "stock_delivery_treatment_confirmed_by_source": "",
        "stock_delivery_treatment_remark": "",
        "raw_materials_not_affect_box": "",
        "raw_materials_use_in_other_products_box": "",
        "raw_materials_scrap_box": "",
        "raw_materials_rework_box": "",
        "raw_materials_use_up_box": "",
        "raw_materials_treatment_remark": "",
        "parts_subassemble_not_affect_box": "",
        "parts_subassemble_use_in_other_products_box": "",
        "parts_subassemble_scrap_box": "",
        "parts_subassemble_rework_box": "",
        "parts_subassemble_use_up_box": "",
        "parts_subassemble_treatment_remark": "",
        "finished_goods_inhouse_not_affect_box": "",
        "finished_goods_inhouse_scrap_box": "",
        "finished_goods_inhouse_rework_box": "",
        "finished_goods_inhouse_use_up_box": "",
        "finished_goods_inhouse_treatment_remark": "",
        "finished_goods_rdc_not_affect_box": "",
        "finished_goods_rdc_scrap_box": "",
        "finished_goods_rdc_rework_box": "",
        "finished_goods_rdc_use_up_box": "",
        "finished_goods_rdc_treatment_remark": "",
        "finished_goods_customer_not_affect_box": "",
        "finished_goods_customer_recall_box": "",
        "finished_goods_customer_rework_box": "",
        "finished_goods_customer_treatment_remark": "",
        "trial_run_value": "",
        "trial_run_plan_finish_date": "",
        "trial_run_resp_person": "",
        "trial_run_resp_source": "",
        "trial_run_comments": "",
        "capability_cmk_value": "",
        "capability_cmk_plan_finish_date": "",
        "capability_cmk_resp_person": "",
        "capability_cmk_resp_source": "",
        "capability_cmk_comments": "",
        "capability_msa_value": "",
        "capability_msa_plan_finish_date": "",
        "capability_msa_resp_person": "",
        "capability_msa_resp_source": "",
        "capability_msa_comments": "",
        "mae_release_value": "",
        "mae_release_plan_finish_date": "",
        "mae_release_resp_person": "",
        "mae_release_resp_source": "",
        "mae_release_comments": "",
        "cleanness_test_value": "",
        "cleanness_test_plan_finish_date": "",
        "cleanness_test_resp_person": "",
        "cleanness_test_resp_source": "",
        "cleanness_test_comments": "",
        "qz_test_value": "",
        "qz_test_plan_finish_date": "",
        "qz_test_resp_person": "",
        "qz_test_resp_source": "",
        "qz_test_comments": "",
        "pdl_200h_value": "",
        "pdl_200h_plan_finish_date": "",
        "pdl_200h_resp_person": "",
        "pdl_200h_resp_source": "",
        "pdl_200h_comments": "",
        "bom_check_value": "",
        "bom_check_plan_finish_date": "",
        "bom_check_resp_person": "",
        "bom_check_resp_source": "",
        "bom_check_comments": "",
        "test_report_value": "",
        "test_report_plan_finish_date": "",
        "test_report_resp_person": "",
        "test_report_resp_source": "",
        "test_report_comments": "",
        "pav_release_value": "",
        "pav_release_plan_finish_date": "",
        "pav_release_resp_person": "",
        "pav_release_resp_source": "",
        "pav_release_comments": "",
        "interface_fmea_value": "",
        "interface_fmea_resp_person": "",
        "interface_fmea_resp_source": "",
        "interface_fmea_due_date": "",
        "product_fmea_value": "",
        "product_fmea_resp_person": "",
        "product_fmea_resp_source": "",
        "product_fmea_due_date": "",
        "special_characteristics_value": "",
        "special_characteristics_resp_person": "",
        "special_characteristics_resp_source": "",
        "special_characteristics_due_date": "",
        "imds_value": "",
        "imds_resp_person": "",
        "imds_resp_source": "",
        "imds_due_date": "",
        "offer_drawing_value": "",
        "offer_drawing_resp_person": "",
        "offer_drawing_resp_source": "",
        "offer_drawing_due_date": "",
        "tcd_value": "",
        "tcd_resp_person": "",
        "tcd_resp_source": "",
        "tcd_due_date": "",
        "norm_wb_hf_value": "",
        "norm_wb_hf_resp_person": "",
        "norm_wb_hf_resp_source": "",
        "norm_wb_hf_due_date": "",
        "affected_document_other_value": "",
        "affected_document_other_resp_person": "",
        "affected_document_other_resp_source": "",
        "affected_document_other_due_date": "",
        "affected_document_other_description": "",
        "development_confirmation": "",
        "dev_bom_yn": "",
        "dev_bom_responsible": "",
        "dev_bom_responsible_source": "",
        "dev_bom_due_date": "",
        "dev_doc_update_yn": "",
        "dev_doc_update_responsible": "",
        "dev_doc_update_responsible_source": "",
        "dev_doc_update_due_date": "",
        "dev_offer_drawing_tcd_dfmea_yn": "",
        "dev_offer_drawing_tcd_dfmea_responsible": "",
        "dev_offer_drawing_tcd_dfmea_responsible_source": "",
        "dev_offer_drawing_tcd_dfmea_due_date": "",
        "dev_norm_wb_hf_yn": "",
        "dev_norm_wb_hf_responsible": "",
        "dev_norm_wb_hf_responsible_source": "",
        "dev_norm_wb_hf_due_date": "",
        "dev_moc_imds_yn": "",
        "dev_moc_imds_responsible": "",
        "dev_moc_imds_responsible_source": "",
        "dev_moc_imds_due_date": "",
        "mfg_equipment_ready_yn": "",
        "mfg_equipment_ready_responsible": "",
        "mfg_equipment_ready_responsible_source": "",
        "mfg_equipment_ready_due_date": "",
        "mfg_program_ready_yn": "",
        "mfg_program_ready_responsible": "",
        "mfg_program_ready_responsible_source": "",
        "mfg_program_ready_due_date": "",
        "mfg_tooling_fixture_ready_yn": "",
        "mfg_tooling_fixture_ready_responsible": "",
        "mfg_tooling_fixture_ready_responsible_source": "",
        "mfg_tooling_fixture_ready_due_date": "",
        "mfg_old_tooling_disposal_yn": "",
        "mfg_old_tooling_disposal_responsible": "",
        "mfg_old_tooling_disposal_responsible_source": "",
        "mfg_old_tooling_disposal_due_date": "",
        "mfg_old_materials_disposal_yn": "",
        "mfg_old_materials_disposal_responsible": "",
        "mfg_old_materials_disposal_responsible_source": "",
        "mfg_old_materials_disposal_due_date": "",
        "mfg_planning_sheet_update_yn": "",
        "mfg_planning_sheet_update_responsible": "",
        "mfg_planning_sheet_update_responsible_source": "",
        "mfg_planning_sheet_update_due_date": "",
        "mfg_fmea_update_yn": "",
        "mfg_fmea_update_responsible": "",
        "mfg_fmea_update_responsible_source": "",
        "mfg_fmea_update_due_date": "",
        "mfg_cpfc_update_yn": "",
        "mfg_cpfc_update_responsible": "",
        "mfg_cpfc_update_responsible_source": "",
        "mfg_cpfc_update_due_date": "",
        "mfg_wi_pds_update_yn": "",
        "mfg_wi_pds_update_responsible": "",
        "mfg_wi_pds_update_responsible_source": "",
        "mfg_wi_pds_update_due_date": "",
        "mfg_first_batch_mark_inside_package_yn": "",
        "mfg_first_batch_mark_inside_package_responsible": "",
        "mfg_first_batch_mark_inside_package_responsible_source": "",
        "mfg_first_batch_mark_inside_package_due_date": "",
        "mfg_first_batch_mark_outside_package_yn": "",
        "mfg_first_batch_mark_outside_package_responsible": "",
        "mfg_first_batch_mark_outside_package_responsible_source": "",
        "mfg_first_batch_mark_outside_package_due_date": "",
        "mfg_training_yn": "",
        "mfg_training_responsible": "",
        "mfg_training_responsible_source": "",
        "mfg_training_due_date": "",
        "cos_storage_old_parts_new_rm_intro_yn": "",
        "cos_storage_old_parts_new_rm_intro_responsible": "",
        "cos_storage_old_parts_new_rm_intro_responsible_source": "",
        "cos_storage_old_parts_new_rm_intro_due_date": "",
        "cos_delivery_old_parts_first_new_fg_yn": "",
        "cos_delivery_old_parts_first_new_fg_responsible": "",
        "cos_delivery_old_parts_first_new_fg_responsible_source": "",
        "cos_delivery_old_parts_first_new_fg_due_date": "",
        "cos_ckd_material_order_sample_orders_yn": "",
        "cos_ckd_material_order_sample_orders_responsible": "",
        "cos_ckd_material_order_sample_orders_responsible_source": "",
        "cos_ckd_material_order_sample_orders_due_date": "",
        "cos_production_scheduling_alignment_yn": "",
        "cos_production_scheduling_alignment_responsible": "",
        "cos_production_scheduling_alignment_responsible_source": "",
        "cos_production_scheduling_alignment_due_date": "",
        "cos_old_stock_inventory_handling_yn": "",
        "cos_old_stock_inventory_handling_responsible": "",
        "cos_old_stock_inventory_handling_responsible_source": "",
        "cos_old_stock_inventory_handling_due_date": "",
        "cos_first_delivery_to_pmo_yn": "",
        "cos_first_delivery_to_pmo_responsible": "",
        "cos_first_delivery_to_pmo_responsible_source": "",
        "cos_first_delivery_to_pmo_due_date": "",
        "cos_ckd_purchasing_parts_sample_orders_yn": "",
        "cos_ckd_purchasing_parts_sample_orders_responsible": "",
        "cos_ckd_purchasing_parts_sample_orders_responsible_source": "",
        "cos_ckd_purchasing_parts_sample_orders_due_date": "",
        "purchasing_internal_departments_requirements_yn": "",
        "purchasing_internal_departments_requirements_responsible": "",
        "purchasing_internal_departments_requirements_responsible_source": "",
        "purchasing_internal_departments_requirements_due_date": "",
        "quality_incoming_inspection_plan_update_yn": "",
        "quality_incoming_inspection_plan_update_responsible": "",
        "quality_incoming_inspection_plan_update_responsible_source": "",
        "quality_incoming_inspection_plan_update_due_date": "",
        "quality_testing_program_update_yn": "",
        "quality_testing_program_update_responsible": "",
        "quality_testing_program_update_responsible_source": "",
        "quality_testing_program_update_due_date": "",
        "quality_ckd_inspection_plan_update_yn": "",
        "quality_ckd_inspection_plan_update_responsible": "",
        "quality_ckd_inspection_plan_update_responsible_source": "",
        "quality_ckd_inspection_plan_update_due_date": "",
        "cpjm_offer_drawing_tcd_customer_yn": "",
        "cpjm_offer_drawing_tcd_customer_responsible": "",
        "cpjm_offer_drawing_tcd_customer_responsible_source": "",
        "cpjm_offer_drawing_tcd_customer_due_date": "",
        "lop_10_digit_material_order_check_yn": "",
        "lop_10_digit_material_order_check_responsible": "",
        "lop_10_digit_material_order_check_responsible_source": "",
        "lop_10_digit_material_order_check_due_date": "",
        "pmo_customer_order_sample_orders_yn": "",
        "pmo_customer_order_sample_orders_responsible": "",
        "pmo_customer_order_sample_orders_responsible_source": "",
        "pmo_customer_order_sample_orders_due_date": "",
        "pmo_customer_first_delivery_information_yn": "",
        "pmo_customer_first_delivery_information_responsible": "",
        "pmo_customer_first_delivery_information_responsible_source": "",
        "pmo_customer_first_delivery_information_due_date": "",
        "other_hw_sw_actions_1_yn": "",
        "other_hw_sw_actions_1_description": "",
        "other_hw_sw_actions_1_responsible": "",
        "other_hw_sw_actions_1_responsible_source": "",
        "other_hw_sw_actions_1_due_date": "",
        "other_hw_sw_actions_2_yn": "",
        "other_hw_sw_actions_2_description": "",
        "other_hw_sw_actions_2_responsible": "",
        "other_hw_sw_actions_2_responsible_source": "",
        "other_hw_sw_actions_2_due_date": "",
        "planned_implementation_date": "",
        "approval_development": "",
        "approval_purchasing": "",
        "approval_mfe": "",
        "approval_quality": "",
        "approval_cpjm": "",
        "approval_cos": "",
        "approval_moex": "",
        "approval_log": "",
        "approval_others": "",
        "approval_other": "",
        "approval_development_person": "",
        "approval_purchasing_person": "",
        "approval_mfe_person": "",
        "approval_cos_person": "",
        "approval_quality_person": "",
        "approval_cpjm_person": "",
        "approval_moex_person": "",
        "approval_log_person": "",
        "approval_other_person": "",
        "approval_note": "",
        "revision_1_nr": "1",
        "revision_1_change_content": data.get("change_proposal", ""),
        "revision_1_version": "V1.0",
        "revision_1_date": data.get("date", ""),
        "revision_1_editor": data.get("initiator", ""),
        "revision_2_nr": "2",
        "revision_2_change_content": "",
        "revision_2_version": "",
        "revision_2_date": "",
        "revision_2_editor": "",
        "revision_description": "",
        "affected_action_me_check_point": "",
        "affected_action_me_specific_analysis_points": "",
        "affected_action_me_discussion_result": "",
        "affected_action_hw_check_point": "",
        "affected_action_hw_specific_analysis_points": "",
        "affected_action_hw_discussion_result": "",
        "affected_action_sw_impact_check_point": "",
        "affected_action_sw_impact_specific_analysis_points": "",
        "affected_action_sw_impact_discussion_result": "",
        "affected_action_sw_implementation_check_point": "",
        "affected_action_sw_implementation_specific_analysis_points": "",
        "affected_action_sw_implementation_discussion_result": "",
        "affected_action_sw_label_traceability_check_point": "",
        "affected_action_sw_label_traceability_specific_analysis_points": "",
        "affected_action_sw_label_traceability_discussion_result": "",
        "affected_action_summary": "",
    }

    schema_text = json.dumps(output_schema, ensure_ascii=False, indent=2)
    user_input_text = json.dumps(data, ensure_ascii=False, indent=2)

    return f"""
你是一个专业的 PD-ECR 工程变更报告分析助手。

你的任务是：根据【用户输入信息】和【历史 PD-ECR 知识库检索内容】，生成一份结构化 PD-ECR 工程变更报告 JSON。

====================
【硬性输出要求】
====================

1. 必须只输出一个完整 JSON 对象。
2. 不要输出 Markdown。
3. 不要输出 ```json。
4. 不要输出解释文字。
5. 不要把 JSON 放进字符串里。
6. 不要转义双引号。
7. JSON 字段名必须完整保留，不要新增无关字段，不要删除字段。
8. 用户已经填写的字段必须保留，不要随意改写。
9. 用户没有填写的分析类内容，请根据历史案例和工程变更逻辑补全。
10. 不要输出“未提供”“无法判断”“AI”。
11. 所有 xxx_value 字段最终必须输出 "yes" 或 "no"。
12. 所有 xxx_yn 字段最终必须输出 "Y" 或 "N"。
13. 所有 approval_xxx 字段最终只能输出 "Required" 或 ""。
14. 所有 checkbox 字段最终只能输出 "☑" 或 "☐"。
15. 不要输出 "yes/no"。
16. 不要输出 "Y/N"。
17. 不要遗漏任何字段。
18. 输出内容要适合后续填充 HTML / Word / PDF 模板。

注意：
- JSON 模板中的空字符串 "" 表示需要你填写，不代表最终可以为空。
- 除非字段确实不适用，否则需要根据历史案例或工程规则给出合理结果。
- 不能因为模板里为空就输出空值。
- 不能凭空编造人名。

====================
【字段生成优先级】
====================

所有字段必须严格遵守以下优先级：

第 1 优先级：用户输入信息
- 用户已经填写的 basic_info 和 change_request 字段必须原样保留。
- 如果用户输入和历史案例冲突，以用户输入为准。

第 2 优先级：相似历史案例
- 如果历史知识库中检索到相似 PD-ECR 案例，并且该案例中某个字段有明确勾选结果、Y/N 结果、负责人、签字人、验证项目、审批部门，则必须优先采用历史案例。
- 不允许用工程常识覆盖历史案例中已经明确存在的勾选结果。
- 特别是 Check Item、Implementation Checklist、Affected Documents、Quality Assurance Items、Approval 部分，应优先参考相似历史案例。

第 3 优先级：工程规则推理
- 只有当历史案例中没有对应字段、字段为空、或历史案例与用户输入明显冲突时，才允许根据工程判断规则推理。

第 4 优先级：部门兜底
- 该规则只适用于 Responsible / Confirmed by / Owner 等任务责任字段。
- 不适用于 approval_xxx_person 签字人字段。
- approval_xxx_person 字段只能填写具体人员姓名。
- 如果 approval_xxx_person 没有从历史案例中检索到具体人名，必须保持空字符串 ""。
- 不允许把 Development、Quality、MFE、Manufacturing、Purchasing、LOG、COS、MOEx、CPjM、PMO、LOP 等部门名填入 approval_xxx_person。

====================
【RAG 使用规则】
====================

1. 历史知识库检索内容不得覆盖用户已填写字段。
2. 用户输入字段优先级最高。
3. 如果历史案例和用户输入冲突，以用户输入为准。
4. 对于以下字段，历史案例优先级高于工程常识推理：
   - function_performance_value
   - interface_appearance_value
   - reliability_robustness_value
   - other_components_value
   - manufacturing_assembly_testing_value
   - supplier_part_value
   - system_hw_sw_calibration_mechanical_value
   - mixed_deliveries_value
   - trial_run_value
   - capability_cmk_value
   - capability_msa_value
   - mae_release_value
   - cleanness_test_value
   - qz_test_value
   - pdl_200h_value
   - bom_check_value
   - test_report_value
   - pav_release_value
   - interface_fmea_value
   - product_fmea_value
   - special_characteristics_value
   - imds_value
   - offer_drawing_value
   - tcd_value
   - norm_wb_hf_value
   - affected_document_other_value
   - all xxx_yn fields
   - all responsible fields
   - all confirmed_by fields
   - all approval_xxx fields

5. 如果历史知识库中检索到相似案例，并且该字段有明确勾选结果，必须复制历史案例的 yes/no 或 Y/N 结果。
6. 如果历史案例中相似变更勾选了某个检查项，当前案例相似时应优先参考该选择。
7. 如果历史案例没有对应字段，才使用工程判断规则。
8. 如果使用历史案例，请在对应 source 字段中填写：
   - "根据历史案例推荐"
9. 如果没有找到具体负责人，仅能判断部门，请在对应 source 字段中填写：
   - "未检索到具体负责人，按责任部门兜底"
10. 如果完全根据工程规则推理，请在对应 source 字段中填写：
   - "根据工程规则推理"
11. 如果历史案例中能识别来源文件名，请填写 source_file 或 evidence。
12. 不要复制历史案例中的 DC No.、日期、产品号、客户项目号。
13. 但是以下字段允许并且应优先复制相似历史案例中的具体人名：
   - Confirmed by
   - Responsible
   - Approver
   - 负责人
   - 确认人
   - 签字人
   - Editor
   - Owner

====================
【负责人 / 签字人推荐规则】
====================

1. Responsible / Confirmed by / Approver / 负责人 / 确认人 / 签字人字段，优先填写历史知识库中相似案例出现过的具体负责人姓名。
2. 如果历史案例中能找到具体人名，必须填写具体人名，不要只写部门。
3. 如果历史案例中没有找到具体人名：
   - Responsible / Confirmed by / Owner 等任务责任字段可以填写责任部门；
   - approval_xxx_person 签字人字段必须保持空字符串 ""，不能填写部门。
4. 不要凭空编造人名。
5. 不要把“Development / Quality / MFE / Purchasing”等部门误当成历史人名。
6. 如果只能填写部门，需要在 source 字段标注：
   "未检索到具体负责人，按责任部门兜底"
7. 如果来自历史案例，需要在 source 字段标注：
   "根据历史案例推荐"

====================
【Step 4 审批人字段规则】
====================

approval_development_person、approval_purchasing_person、approval_te_person、
approval_cos_person、approval_quality_person、approval_cpjm_person、
approval_moex_person、approval_log_person 只能填写具体人员姓名。

严禁把以下内容填入 approval_xxx_person 字段：
1. 部门名称，例如 Development、Purchasing、TE、COS、Quality、CPjM、MOEx、LOG；
2. 职能名称，例如 研发、采购、工艺、样品、质量、客户项目、生产、物流；
3. 动作或分析项，例如 影响分析、加工、装配、测试、工程师、验证、风险分析；
4. Others、in needed、N/A 等非人名内容。

如果知识库中没有检索到具体人员姓名，则 approval_xxx_person 必须填空字符串 ""，
同时 approval_xxx_person_source 填 "not_found"。

====================
【Check Item 判断规则】
====================

对于以下 7 个 Check Item：

1. function_performance_value
2. interface_appearance_value
3. reliability_robustness_value
4. other_components_value
5. manufacturing_assembly_testing_value
6. supplier_part_value
7. system_hw_sw_calibration_mechanical_value

必须按以下顺序判断：

第一步：查看历史案例是否有相同或相似变更。
- 如果有，并且历史案例中该项为 Yes，则输出 "yes"。
- 如果有，并且历史案例中该项为 No，则输出 "no"。
- confirmed_by 优先复制历史案例中的具体确认人。
- 如果历史案例只有部门，则填写部门。

第二步：如果历史案例没有明确结果，再根据工程规则判断：
- 涉及功能、性能、结构、材料、尺寸、客户要求：function_performance_value = "yes"
- 涉及外观、接口、安装边界、连接方式、配合关系：interface_appearance_value = "yes"
- 涉及可靠性、耐久、寿命、稳定性、鲁棒性、压装风险、卡滞风险、质量风险：reliability_robustness_value = "yes"
- 涉及关联零件、同步变更、系统匹配、周边零件影响：other_components_value = "yes"
- 涉及加工、装配、测试、工装、设备、产线、工艺文件、压装过程：manufacturing_assembly_testing_value = "yes"
- 涉及采购件、供应商零件、外协件、来料检验、供应商图纸：supplier_part_value = "yes"
- 涉及 System / Hardware / Software / Calibration / Mechanical alignment：system_hw_sw_calibration_mechanical_value = "yes"

【Confirmed by / 确认人字段规则】

以下 confirmed_by 字段只能填写具体人员姓名，不能填写部门名称：

function_performance_confirmed_by
interface_appearance_confirmed_by
reliability_robustness_confirmed_by
other_components_confirmed_by
manufacturing_assembly_testing_confirmed_by
supplier_part_confirmed_by
system_hw_sw_calibration_mechanical_confirmed_by
stock_delivery_treatment_confirmed_by

严禁把以下内容填入 confirmed_by 字段：
Development、研发、Quality、质量、MFE、工艺、Manufacturing、生产、
Purchasing、采购、LOG、物流、COS、样品、CPjM、客户项目、MOEx。

如果历史知识库中没有检索到具体确认人姓名，则 confirmed_by 字段必须填空字符串 ""。
不要使用部门兜底。
不要凭空编造人名。

【Affected Documents 判断规则】

1. Step 3.3 Affected Documents 必须优先复制历史案例中的 No / Yes 勾选结果。
2. 如果历史案例中某一项明确勾选 No，则当前字段必须输出 "no"。
3. 如果历史案例中某一项明确勾选 Yes，则当前字段必须输出 "yes"。
4. 不允许因为工程常识把历史案例中的 No 改成 Yes。
5. 只有当历史知识库完全没有检索到 Step 3.3 表格时，才允许根据当前变更内容进行工程推理。
6. 如果根据工程规则推理，但证据不足，应保守输出 "no"。
7. Responsible / 负责人字段只有在历史案例中有具体负责人时才填写；没有检索到具体负责人则保持空字符串 ""。
8. 不要用 Development、Quality、MFE、Purchasing 等部门作为负责人兜底。

====================
【Implementation Checklist 判断规则】
====================

1. 所有 xxx_yn 字段必须输出 "Y" 或 "N"。
2. 如果历史案例有明确 Y/N，优先复制历史案例。
3. 如果没有历史案例，再根据当前变更内容推理。
4. 如果某项为 "Y"，对应 responsible 字段必须填写具体负责人或责任部门。
5. 如果某项为 "N"，对应 responsible 可以为空，也可以填写责任部门。
6. 如果历史案例中有具体负责人姓名，优先填写具体姓名。
7. 如果没有具体姓名，填写责任部门。
8. source 字段需要标注来源。

====================
【Quality Assurance Items 判断规则】
====================

1. 如果涉及质量验证、可靠性测试、测试报告、Trial run、CMK、MSA、MAE release，应补充 Quality Assurance Items。
2. 如果历史案例中有明确结果，优先复制历史案例。
3. 常见责任部门：
   - Trial run: MFE / Manufacturing
   - CMK: Quality
   - MSA: Quality
   - MAE release: MFE
   - Cleanness test: Quality
   - QZ test: Quality
   - PDL 200h: Quality / Development
   - BOM check: Development
   - Test report: Quality / Development
   - PAV release: Quality

====================
【Cost / Stock 判断规则】
====================

1. cost_increase_box、cost_decrease_box、cost_no_change_box 三者只能有一个为 "☑"，其他为 "☐"。
2. 如果历史案例有明确成本变化，优先复制历史案例。
3. 如果没有历史案例，且用户没有说明成本变化，默认：
   - cost_no_change_box = "☑"
   - cost_increase_box = "☐"
   - cost_decrease_box = "☐"
4. 库存处理相关 checkbox 同组只能有一个或合理多个被选中。
5. 如果没有库存影响，not_affect_box 通常为 "☑"。

【Step 7 Implementation Approval 签字人规则】

1. Step 7 Implementation Approval / 导入清单 中，各部门字段必须填写历史案例中的具体签字人姓名，不是填写 Required。
2. 如果历史案例中存在 Step 7 / Implementation Approval / 导入清单 / 签字栏 / Approval 表格，必须优先复制其中的部门对应签字人。
3. 部门字段映射如下：
   - Development / 研发 -> approval_development_person
   - Purchasing / 采购 -> approval_purchasing_person
   - MFE / 工艺 -> approval_mfe_person
   - COS / 样品 -> approval_cos_person
   - Quality / 质量 -> approval_quality_person
   - CPjM / 客户项目 -> approval_cpjm_person
   - MOEx / 生产 -> approval_moex_person
   - LOG / 物流 -> approval_log_person
   - Other / 其他 -> approval_other_person
4. 如果历史案例中检索到具体人名，必须填写具体人名，不要填写 Required。
5. 如果没有检索到具体人名，则对应 approval_xxx_person 保持空字符串 ""。
6. 不要用部门名作为签字人兜底。
7. 不要凭空编造签字人。

====================
【历史 PD-ECR 知识库检索内容】
====================

{rag_context if rag_context else "无相关历史案例。"}

====================
【用户输入信息】
====================

{user_input_text}

====================
【必须输出的 JSON 结构】
====================

请严格按照下面 JSON 结构输出。
字段名必须完整保留。
空字符串字段必须根据历史案例或工程规则补全。
最终只能输出 JSON 对象。

{schema_text}
"""


async def call_llm(data: Dict[str, Any], rag_context: str = "") -> Dict[str, Any]:
    client = get_llm_client()
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是一个严谨的工程变更报告生成助手，只输出合法 JSON。必须优先保留用户输入，并参考历史案例补全分析内容。",
            },
            {
                "role": "user",
                "content": build_prompt(data, rag_context),
            },
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content
    content = clean_json_text(content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "大模型返回的不是合法 JSON",
                "raw_output": content,
            },
        )


def render_markdown_to_html_page(markdown_content: str, title: str) -> str:
    body_html = markdown.markdown(
        markdown_content,
        extensions=[
            "tables",
            "fenced_code",
            "nl2br",
            "toc",
        ],
    )

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{
      font-family: "Microsoft YaHei", Arial, sans-serif;
      background: #f3f5f7;
      margin: 0;
      padding: 0;
      color: #222;
    }}

    .topbar {{
      background: #ffffff;
      border-bottom: 1px solid #ddd;
      padding: 18px 42px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 10;
    }}

    .bosch {{
      color: #d40000;
      font-weight: bold;
      font-size: 26px;
      letter-spacing: 1px;
    }}

    .title {{
      font-size: 22px;
      font-weight: bold;
      margin-top: 4px;
    }}

    .actions button {{
      margin-left: 10px;
      padding: 8px 18px;
      cursor: pointer;
      border: 1px solid #bbb;
      background: white;
      border-radius: 4px;
    }}

    .actions button:hover {{
      background: #f2f2f2;
    }}

    .report {{
      width: 88%;
      max-width: 1200px;
      margin: 32px auto;
      background: #ffffff;
      padding: 42px 56px;
      border: 1px solid #ddd;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }}

    h1 {{
      font-size: 26px;
      border-bottom: 3px solid #d40000;
      padding-bottom: 10px;
      margin-top: 10px;
      color: #111;
    }}

    h2 {{
      font-size: 21px;
      margin-top: 32px;
      padding-left: 12px;
      border-left: 5px solid #d40000;
      color: #222;
    }}

    h3 {{
      font-size: 17px;
      margin-top: 24px;
      color: #333;
    }}

    p {{
      font-size: 15px;
      line-height: 1.8;
      margin: 10px 0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0 26px 0;
      font-size: 14px;
      background: white;
    }}

    th {{
      background: #eef2f7;
      font-weight: bold;
      text-align: left;
    }}

    th, td {{
      border: 1px solid #b8b8b8;
      padding: 9px 10px;
      vertical-align: top;
      line-height: 1.6;
    }}

    tr:nth-child(even) td {{
      background: #fafafa;
    }}

    code {{
      background: #f1f1f1;
      padding: 2px 5px;
      border-radius: 3px;
      font-family: Consolas, monospace;
    }}

    pre {{
      background: #f7f7f7;
      border: 1px solid #ddd;
      padding: 14px;
      overflow-x: auto;
      border-radius: 4px;
    }}

    hr {{
      border: none;
      border-top: 1px solid #ddd;
      margin: 34px 0;
    }}

    ul {{
      line-height: 1.8;
    }}

    @media print {{
      .topbar {{
        display: none;
      }}

      body {{
        background: white;
      }}

      .report {{
        width: 100%;
        max-width: none;
        margin: 0;
        padding: 20px;
        border: none;
        box-shadow: none;
      }}
    }}
  </style>
</head>

<body>
  <div class="topbar">
    <div>
      <div class="bosch">BOSCH</div>
      <div class="title">{title}</div>
    </div>
    <div class="actions">
      <button onclick="window.print()">打印 / 保存 PDF</button>
      <button onclick="window.history.back()">返回</button>
    </div>
  </div>

  <div class="report">
    {body_html}
  </div>
</body>
</html>
"""


def normalize_yes_no_value(value: Any) -> str:
    value = str(value or "").strip().lower()

    yes_values = ["yes", "y", "true", "1", "是", "有", "需要", "影响", "required"]
    no_values = [
        "no",
        "n",
        "false",
        "0",
        "否",
        "无",
        "不需要",
        "不影响",
        "not required",
    ]

    if value in yes_values:
        return "yes"

    if value in no_values:
        return "no"

    return "no"


def apply_all_yes_no_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    yes_no_prefixes = [
        # Step 3.1 Impact check
        "function_performance",
        "interface_appearance",
        "reliability_robustness",
        "other_components",
        "manufacturing_assembly_testing",
        "supplier_part",
        "system_hw_sw_calibration_mechanical",
        # Stock / delivery
        "mixed_deliveries",
        # Step 3.2 Quality Assurance Items
        "trial_run",
        "capability_cmk",
        "capability_msa",
        "mae_release",
        "cleanness_test",
        "qz_test",
        "pdl_200h",
        "bom_check",
        "test_report",
        "pav_release",
        # Step 3.3 Affected Documents
        "interface_fmea",
        "product_fmea",
        "special_characteristics",
        "imds",
        "offer_drawing",
        "tcd",
        "norm_wb_hf",
        "affected_document_other",
    ]

    for prefix in yes_no_prefixes:
        value_key = f"{prefix}_value"
        yes_key = f"{prefix}_yes_box"
        no_key = f"{prefix}_no_box"
        box_key = f"{prefix}_box"

        value = normalize_yes_no_value(result.get(value_key, "no"))
        result[value_key] = value

        yes_box = "☑" if value == "yes" else "☐"
        no_box = "☑" if value == "no" else "☐"

        result[yes_key] = yes_box
        result[no_key] = no_box

        # 兼容旧模板里 xxx_box 的写法
        result[box_key] = yes_box

    return result


def normalize_stock_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    库存处理项不是 xxx_value 结构，而是直接 checkbox 字段。
    如果某组完全没勾选，则默认 Not Affect。
    """

    groups = {
        "raw_materials": [
            "raw_materials_not_affect_box",
            "raw_materials_use_in_other_products_box",
            "raw_materials_scrap_box",
            "raw_materials_rework_box",
            "raw_materials_use_up_box",
        ],
        "parts_subassemble": [
            "parts_subassemble_not_affect_box",
            "parts_subassemble_use_in_other_products_box",
            "parts_subassemble_scrap_box",
            "parts_subassemble_rework_box",
            "parts_subassemble_use_up_box",
        ],
        "finished_goods_inhouse": [
            "finished_goods_inhouse_not_affect_box",
            "finished_goods_inhouse_scrap_box",
            "finished_goods_inhouse_rework_box",
            "finished_goods_inhouse_use_up_box",
        ],
        "finished_goods_rdc": [
            "finished_goods_rdc_not_affect_box",
            "finished_goods_rdc_scrap_box",
            "finished_goods_rdc_rework_box",
            "finished_goods_rdc_use_up_box",
        ],
        "finished_goods_customer": [
            "finished_goods_customer_not_affect_box",
            "finished_goods_customer_recall_box",
            "finished_goods_customer_rework_box",
        ],
    }

    for group_name, fields in groups.items():
        for f in fields:
            if result.get(f) not in ["☑", "☐"]:
                result[f] = "☐"

        has_checked = any(result.get(f) == "☑" for f in fields)

        if not has_checked:
            not_affect_key = f"{group_name}_not_affect_box"
            if not_affect_key in fields:
                result[not_affect_key] = "☑"

    return result


def extract_json_from_llm_result(llm_result):
    """
    防止 call_llm 返回字符串、Markdown 包裹 JSON、或已经是 dict。
    """
    if isinstance(llm_result, dict):
        return llm_result

    if not isinstance(llm_result, str):
        raise ValueError(f"LLM 返回类型异常：{type(llm_result)}")

    text = llm_result.strip()

    if text.startswith("```json"):
        text = text.replace("```json", "", 1).strip()
    if text.startswith("```"):
        text = text.replace("```", "", 1).strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM 返回内容中没有找到合法 JSON：{text[:500]}")

    json_text = text[start : end + 1]
    return json.loads(json_text)


def normalize_date_string(value: str) -> str:
    """
    把 20260407 转成 2026-04-07。
    如果本来就是 2026-04-07，则保持不变。
    """
    value = str(value or "").strip()

    if re.fullmatch(r"\d{8}", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"

    return value


def normalize_text_for_match(text: str) -> str:
    """
    用于匹配历史表格里的 item 名称。
    """
    text = str(text or "").lower()
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = text.replace("–", " ")
    text = text.replace("—", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


QA_ITEM_CONFIG = {
    "trial_run": {
        "aliases": ["try run", "trial run", "trail run"],
        "value_key": "trial_run_value",
        "date_key": "trial_run_plan_finish_date",
        "person_key": "trial_run_resp_person",
        "comment_key": "trial_run_comments",
        "source_key": "trial_run_resp_source",
    },
    "capability_cmk": {
        "aliases": [
            "capability studies cmk",
            "capability studies - cmk",
            "capability studies_ cmk",
            "capability studies_cm k",
            "capability studies_ cmk",
            "capability studies-cmk",
            "cmk",
        ],
        "value_key": "capability_cmk_value",
        "date_key": "capability_cmk_plan_finish_date",
        "person_key": "capability_cmk_resp_person",
        "comment_key": "capability_cmk_comments",
        "source_key": "capability_cmk_resp_source",
    },
    "capability_msa": {
        "aliases": [
            "capability studies msa",
            "capability studies - msa",
            "capability studies_ msa",
            "capability studies-msa",
            "msa",
        ],
        "value_key": "capability_msa_value",
        "date_key": "capability_msa_plan_finish_date",
        "person_key": "capability_msa_resp_person",
        "comment_key": "capability_msa_comments",
        "source_key": "capability_msa_resp_source",
    },
    "mae_release": {
        "aliases": ["mae release"],
        "value_key": "mae_release_value",
        "date_key": "mae_release_plan_finish_date",
        "person_key": "mae_release_resp_person",
        "comment_key": "mae_release_comments",
        "source_key": "mae_release_resp_source",
    },
    "cleanness_test": {
        "aliases": ["cleanness test", "cleanliness test"],
        "value_key": "cleanness_test_value",
        "date_key": "cleanness_test_plan_finish_date",
        "person_key": "cleanness_test_resp_person",
        "comment_key": "cleanness_test_comments",
        "source_key": "cleanness_test_resp_source",
    },
    "qz_test": {
        "aliases": ["qz test"],
        "value_key": "qz_test_value",
        "date_key": "qz_test_plan_finish_date",
        "person_key": "qz_test_resp_person",
        "comment_key": "qz_test_comments",
        "source_key": "qz_test_resp_source",
    },
    "pdl_200h": {
        "aliases": ["200h pdl", "pdl 200h", "200 h pdl"],
        "value_key": "pdl_200h_value",
        "date_key": "pdl_200h_plan_finish_date",
        "person_key": "pdl_200h_resp_person",
        "comment_key": "pdl_200h_comments",
        "source_key": "pdl_200h_resp_source",
    },
    "bom_check": {
        "aliases": ["bom check", "bom"],
        "value_key": "bom_check_value",
        "date_key": "bom_check_plan_finish_date",
        "person_key": "bom_check_resp_person",
        "comment_key": "bom_check_comments",
        "source_key": "bom_check_resp_source",
    },
    "test_report": {
        "aliases": ["test report", "test repot"],
        "value_key": "test_report_value",
        "date_key": "test_report_plan_finish_date",
        "person_key": "test_report_resp_person",
        "comment_key": "test_report_comments",
        "source_key": "test_report_resp_source",
    },
    "pav_release": {
        "aliases": ["pav release"],
        "value_key": "pav_release_value",
        "date_key": "pav_release_plan_finish_date",
        "person_key": "pav_release_resp_person",
        "comment_key": "pav_release_comments",
        "source_key": "pav_release_resp_source",
    },
}


def detect_qa_item_key(line: str) -> str:
    """
    从历史知识库的一行文本里判断对应哪个 QA item。
    """
    norm_line = normalize_text_for_match(line)

    for item_key, cfg in QA_ITEM_CONFIG.items():
        for alias in cfg["aliases"]:
            norm_alias = normalize_text_for_match(alias)
            if norm_alias and norm_alias in norm_line:
                return item_key

    return ""


def parse_history_line_for_qa(line: str) -> dict:
    """
    从历史知识库的一行里尽量提取：
    - 是否勾选
    - 日期
    - 负责人
    - 备注

    兼容 Markdown 表格和普通文本。
    """
    raw_line = str(line or "").strip()
    if not raw_line:
        return {}

    item_key = detect_qa_item_key(raw_line)
    if not item_key:
        return {}

    checked_yes = any(
        x in raw_line for x in ["☑", "☒", "[x]", "[X]", "√", "✓", "checked"]
    )
    checked_no = any(x in raw_line for x in ["☐", "[ ]"])

    date = ""
    person = ""
    comment = ""

    # 提取日期：20260407 或 2026-04-07
    date_match = re.search(r"\b(20\d{2}[-/.]?\d{2}[-/.]?\d{2})\b", raw_line)
    if date_match:
        date = normalize_date_string(
            date_match.group(1).replace("/", "-").replace(".", "-")
        )

    # 优先解析 Markdown 表格
    if "|" in raw_line:
        cells = [c.strip() for c in raw_line.split("|") if c.strip()]

        # 尝试找日期所在列
        date_idx = -1
        for idx, cell in enumerate(cells):
            if re.search(r"\b(20\d{2}[-/.]?\d{2}[-/.]?\d{2})\b", cell):
                date_idx = idx
                date = normalize_date_string(
                    re.search(r"\b(20\d{2}[-/.]?\d{2}[-/.]?\d{2})\b", cell)
                    .group(1)
                    .replace("/", "-")
                    .replace(".", "-")
                )
                break

        if date_idx != -1:
            if date_idx + 1 < len(cells):
                person = cells[date_idx + 1].strip()
            if date_idx + 2 < len(cells):
                comment = cells[date_idx + 2].strip()
    else:
        # 普通文本情况：日期后面的英文名尽量识别为负责人
        if date_match:
            after_date = raw_line[date_match.end() :].strip()

            # 按多个空格、tab 切分
            parts = re.split(r"\s{2,}|\t+", after_date)
            parts = [p.strip() for p in parts if p.strip()]

            if parts:
                person_candidate = parts[0]

                # 如果第一个片段太长，尝试只取前两个英文单词作为人名
                name_match = re.match(r"([A-Za-z]+(?:\s+[A-Za-z]+)?)", person_candidate)
                if name_match:
                    person = name_match.group(1).strip()
                    comment = person_candidate[name_match.end() :].strip()
                    if len(parts) > 1:
                        comment = (comment + " " + " ".join(parts[1:])).strip()
                else:
                    comment = person_candidate
                    if len(parts) > 1:
                        comment = " ".join(parts)

    return {
        "item_key": item_key,
        "checked_yes": checked_yes,
        "checked_no": checked_no,
        "date": date,
        "person": person,
        "comment": comment,
        "source": "根据历史案例推荐",
    }


def normalize_quality_items_from_rag(result: dict, rag_context: str) -> dict:
    """
    从 RAG 检索内容中兜底抽取 Quality Assurance Items。
    解决 try run / Trial run / CMK / BOM check 等名称不一致导致的漏填问题。
    """
    if not isinstance(result, dict):
        return result

    if not rag_context:
        return result

    lines = str(rag_context).splitlines()

    for line in lines:
        parsed = parse_history_line_for_qa(line)
        if not parsed:
            continue

        item_key = parsed["item_key"]
        cfg = QA_ITEM_CONFIG[item_key]

        value_key = cfg["value_key"]
        date_key = cfg["date_key"]
        person_key = cfg["person_key"]
        comment_key = cfg["comment_key"]
        source_key = cfg["source_key"]

        has_history_content = any(
            [
                parsed.get("checked_yes"),
                parsed.get("date"),
                parsed.get("person"),
                parsed.get("comment"),
            ]
        )

        if has_history_content:
            result[value_key] = "yes"

        # 如果历史明确没勾，并且没有其他内容，才置 no
        if parsed.get("checked_no") and not has_history_content:
            result[value_key] = "no"

        if parsed.get("date") and not str(result.get(date_key, "")).strip():
            result[date_key] = parsed["date"]

        if parsed.get("person") and not str(result.get(person_key, "")).strip():
            result[person_key] = parsed["person"]

        if parsed.get("comment") and not str(result.get(comment_key, "")).strip():
            result[comment_key] = parsed["comment"]

        if source_key and has_history_content:
            result[source_key] = "根据历史案例推荐"

    return result


def normalize_yes_no_fields(result: dict) -> dict:
    """
    修正 LLM 输出中 value 与日期/负责人/备注不一致的问题。
    只要某个 QA item 有日期、负责人或备注，就自动认为 required = yes。
    """
    if not isinstance(result, dict):
        return result

    for _, cfg in QA_ITEM_CONFIG.items():
        value_key = cfg["value_key"]
        date_key = cfg["date_key"]
        person_key = cfg["person_key"]
        comment_key = cfg["comment_key"]

        # 日期格式统一
        if result.get(date_key):
            result[date_key] = normalize_date_string(result.get(date_key))

        has_content = any(
            [
                str(result.get(date_key, "")).strip(),
                str(result.get(person_key, "")).strip(),
                str(result.get(comment_key, "")).strip(),
            ]
        )

        if has_content:
            result[value_key] = "yes"

        value = str(result.get(value_key, "")).strip().lower()

        if value in ["y", "yes", "true", "1", "是", "需要", "required"]:
            result[value_key] = "yes"
        elif value in ["n", "no", "false", "0", "否", "不需要", "not required"]:
            result[value_key] = "no"
        elif value not in ["yes", "no"]:
            result[value_key] = "no"

    return result


def extract_approval_persons_from_rag(
    result: Dict[str, Any], rag_context: str
) -> Dict[str, Any]:
    """
    从 RAG 文本中抽取 Step 7 / Implementation Approval / Suggested Approvers 签字人。

    兼容几种格式：
    1. Markdown 表格：
       | Development | Purchasing | MFE | COS | Quality | CPjM | MOEx | LOG |
       | TANG Liang | TAO Jiong | HE Yonggang | HE Yonggang | XIA Qian | SU Jian | LUO Zhi | XU Baochun |

    2. 普通文本：
       Development /研发 Purchasing /采购 MFE/工艺 ...
       TANG Liang TAO Jiong HE Yonggang ...

    3. OCR/解析后混合文本。
    """

    if not isinstance(result, dict):
        return result

    if not rag_context:
        return result

    text = str(rag_context)

    dept_order = [
        ("approval_development_person", ["development", "研发"]),
        ("approval_purchasing_person", ["purchasing", "采购"]),
        ("approval_mfe_person", ["mfe", "tef", "工艺"]),
        ("approval_cos_person", ["cos", "样品"]),
        ("approval_quality_person", ["quality", "质量"]),
        ("approval_cpjm_person", ["cpjm", "客户项目"]),
        ("approval_moex_person", ["moex", "生产"]),
        ("approval_log_person", ["log", "物流"]),
    ]

    dept_words = [
        "development",
        "研发",
        "purchasing",
        "采购",
        "mfe",
        "tef",
        "te",
        "工艺",
        "cos",
        "样品",
        "quality",
        "质量",
        "cpjm",
        "客户项目",
        "moex",
        "生产",
        "log",
        "物流",
        "other",
        "others",
        "其他",
    ]

    invalid_words = [
        # 部门 / 职能
        "development",
        "研发",
        "purchasing",
        "采购",
        "mfe",
        "tef",
        "工艺",
        "cos",
        "样品",
        "quality",
        "质量",
        "cpjm",
        "客户项目",
        "moex",
        "生产",
        "log",
        "物流",
        "other",
        "others",
        "其他",
        "department",
        "部门",
        # 非人名 / 表格内容
        "required",
        "not required",
        "n/a",
        "na",
        "none",
        "无",
        "historical",
        "historical pd",
        "pd",
        "pdecr",
        "pd-ecr",
        "ecr",
        "ecr case",
        "case",
        "affect",
        "affect product",
        "affected product",
        "product",
        "qac",
        "impact",
        "check",
        "item",
        "document",
        "responsible",
        "due date",
        "approval",
        "validation",
        "technical feasibility",
        # 中文动作词
        "影响分析",
        "加工",
        "装配",
        "测试",
        "工程师",
        "验证",
        "风险分析",
        "分析",
        "评估",
        "确认",
    ]

    def split_cells(line: str) -> list[str]:
        line = str(line or "").strip()

        if "|" in line:
            return [c.strip() for c in line.split("|") if c.strip()]

        # 先按 tab 或连续空格切
        cells = [c.strip() for c in re.split(r"\t+|\s{2,}", line) if c.strip()]
        if len(cells) > 1:
            return cells

        # 如果整行是普通空格连接，就返回原行，后面用正则抽人名
        return [line]

    def is_department_text(s: str) -> bool:
        low = str(s or "").lower()
        return any(w in low or w in s for w in dept_words)

    def is_separator(line: str) -> bool:
        s = str(line or "").strip()
        if not s:
            return True
        cleaned = s.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
        return cleaned == ""

    def is_person_name(s: str) -> bool:
        s = str(s or "").strip()
        low = s.lower()

        invalid_words = [
            "development",
            "研发",
            "purchasing",
            "采购",
            "mfe",
            "tef",
            "工艺",
            "cos",
            "样品",
            "quality",
            "质量",
            "cpjm",
            "客户项目",
            "moex",
            "生产",
            "log",
            "物流",
            "other",
            "others",
            "其他",
            "historical",
            "historical pd",
            "pd",
            "pdecr",
            "pd-ecr",
            "ecr",
            "ecr case",
            "case",
            "affect",
            "affect product",
            "affected product",
            "product",
            "qac",
            "impact",
            "check",
            "item",
            "document",
            "responsible",
            "due date",
            "approval",
            "validation",
            "technical feasibility",
            "required",
            "n/a",
            "na",
            "none",
            "影响分析",
            "加工",
            "装配",
            "测试",
            "工程师",
            "验证",
            "风险分析",
            "分析",
            "评估",
            "确认",
        ]

        if not s:
            return False

        if any(w in low or w in s for w in invalid_words):
            return False

        if len(s) > 35:
            return False

        # 推荐：公司英文名格式，姓全大写 + 名首字母大写
        # 例如 FENG Ying / TANG Liang / HE Yonggang
        if re.fullmatch(r"[A-Z]{2,}\s+[A-Z][a-z]+", s):
            return True

        # 兼容普通英文名，但不允许全是业务词
        if re.fullmatch(r"[A-Z][a-z]+\s+[A-Z][a-z]+", s):
            return True

        # 中文姓名
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", s):
            return True

        return False

    def extract_names_from_line(line: str) -> list[str]:
        """
        从一行中提取多个英文/中文姓名。
        """
        line = str(line or "").strip()

        # 如果是表格，优先按单元格取
        cells = split_cells(line)
        cell_names = [c for c in cells if is_person_name(c)]
        if len(cell_names) >= 2:
            return cell_names

        # 普通文本中抽英文姓名
        english_names = re.findall(r"\b[A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+\b", line)

        # 中文姓名兜底
        chinese_names = re.findall(
            r"(?<![\u4e00-\u9fff])[\u4e00-\u9fff]{2,4}(?![\u4e00-\u9fff])", line
        )

        names = english_names + chinese_names

        # 过滤部门词
        names = [n.strip() for n in names if is_person_name(n.strip())]

        return names

    def header_score(line: str) -> int:
        low = str(line or "").lower()
        score = 0
        for _, tokens in dept_order:
            if any(t in low or t in line for t in tokens):
                score += 1
        return score

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 方法 1：找“部门表头行”，然后向后找“人名行”
    for i, line in enumerate(lines):
        if is_separator(line):
            continue

        if header_score(line) < 4:
            continue

        header_cells = split_cells(line)

        # 如果表头被拆成多个单元格，建立列映射
        header_keys = []
        for cell in header_cells:
            low = cell.lower()
            matched_key = ""
            for result_key, tokens in dept_order:
                if any(t in low or t in cell for t in tokens):
                    matched_key = result_key
                    break
            if matched_key:
                header_keys.append(matched_key)

        # 向后找人名行
        for j in range(i + 1, min(i + 10, len(lines))):
            row = lines[j]

            if is_separator(row):
                continue

            if "---" in row:
                continue

            # 跳过部门续行
            if header_score(row) >= 3:
                continue

            row_cells = split_cells(row)
            row_names = extract_names_from_line(row)

            # 情况 A：表格单元格数量能对齐
            if len(header_keys) >= 4 and len(row_cells) >= len(header_keys):
                filled = 0
                for idx, result_key in enumerate(header_keys):
                    if idx >= len(row_cells):
                        continue

                    person = row_cells[idx].strip()
                    if is_person_name(person):
                        result[result_key] = person
                        filled += 1

                if filled >= 2:
                    return result

            # 情况 B：普通文本里直接抽到了多个名字，按部门顺序填
            if len(row_names) >= 4:
                for idx, (result_key, _) in enumerate(dept_order):
                    if idx < len(row_names):
                        result[result_key] = row_names[idx]
                return result

    # 方法 2：如果 RAG 里只有人名行，没有清晰表头，但包含常见签字人顺序
    all_names = extract_names_from_line(text)
    if len(all_names) >= 6:
        for idx, (result_key, _) in enumerate(dept_order):
            if idx < len(all_names):
                result[result_key] = all_names[idx]

    return result


def clean_invalid_approval_persons(result: Dict[str, Any]) -> Dict[str, Any]:
    approval_person_keys = [
        "approval_development_person",
        "approval_purchasing_person",
        "approval_mfe_person",
        "approval_cos_person",
        "approval_quality_person",
        "approval_cpjm_person",
        "approval_moex_person",
        "approval_log_person",
        "approval_other_person",
    ]

    invalid_words = [
        "development",
        "研发",
        "purchasing",
        "采购",
        "mfe",
        "tef",
        "工艺",
        "cos",
        "样品",
        "quality",
        "质量",
        "cpjm",
        "客户项目",
        "moex",
        "生产",
        "log",
        "物流",
        "other",
        "others",
        "其他",
        "department",
        "部门",
        "required",
        "not required",
        "n/a",
        "na",
        "none",
        "无",
        "historical",
        "historical pd",
        "pd",
        "pdecr",
        "pd-ecr",
        "ecr",
        "ecr case",
        "case",
        "affect",
        "affect product",
        "affected product",
        "product",
        "qac",
        "impact",
        "check",
        "item",
        "document",
        "responsible",
        "due date",
        "approval",
        "validation",
        "technical feasibility",
        "影响分析",
        "加工",
        "装配",
        "测试",
        "工程师",
        "验证",
        "风险分析",
        "分析",
        "评估",
        "确认",
    ]

    def is_valid_person_name(value: str) -> bool:
        value = str(value or "").strip()
        low = value.lower()

        if not value:
            return False

        if any(w in low or w in value for w in invalid_words):
            return False

        if len(value) > 35:
            return False

        # Bosch 常见英文名格式：FENG Ying / TANG Liang / HE Yonggang
        if re.fullmatch(r"[A-Z]{2,}\s+[A-Z][a-z]+", value):
            return True

        # 兼容：Firstname Lastname，但会更严格过滤
        if re.fullmatch(r"[A-Z][a-z]+\s+[A-Z][a-z]+", value):
            return True

        # 中文姓名
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value):
            return True

        return False

    for key in approval_person_keys:
        value = str(result.get(key, "") or "").strip()

        if not is_valid_person_name(value):
            result[key] = ""

    return result


def clean_invalid_confirmed_by_persons(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理 Step 3 Impact Yes/No Check 里的 confirmed_by 字段。
    confirmed_by 只能是具体人名，不能是部门。
    """

    confirmed_by_keys = [
        "function_performance_confirmed_by",
        "interface_appearance_confirmed_by",
        "reliability_robustness_confirmed_by",
        "other_components_confirmed_by",
        "manufacturing_assembly_testing_confirmed_by",
        "supplier_part_confirmed_by",
        "system_hw_sw_calibration_mechanical_confirmed_by",
        "stock_delivery_treatment_confirmed_by",
    ]

    invalid_words = [
        # 部门 / 职能
        "development",
        "研发",
        "quality",
        "质量",
        "mfe",
        "tef",
        "工艺",
        "manufacturing",
        "生产",
        "purchasing",
        "采购",
        "log",
        "物流",
        "cos",
        "样品",
        "cpjm",
        "客户项目",
        "moex",
        "department",
        "部门",
        # 非人名
        "required",
        "not required",
        "n/a",
        "na",
        "none",
        "无",
        "影响分析",
        "加工",
        "装配",
        "测试",
        "工程师",
        "验证",
        "风险分析",
        "分析",
        "评估",
        "确认",
    ]

    for key in confirmed_by_keys:
        value = str(result.get(key, "") or "").strip()
        low = value.lower()

        if not value:
            continue

        if any(w in low or w in value for w in invalid_words):
            result[key] = ""
            continue

        has_english_name = bool(re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+){1,2}", value))
        has_chinese_name = bool(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value))

        if not has_english_name and not has_chinese_name:
            result[key] = ""

    return result


def build_report_modules(
    user_input: Dict[str, Any],
    llm_result: Dict[str, Any],
    report_url: str = "",
) -> Dict[str, Any]:
    """
    给前端模块化展示使用。
    不影响原来的 HTML 报告生成。
    """

    return {
        "basic_info": {
            "title": "基本信息",
            "description": "展示 PD-ECR 的基础输入信息。",
            "data": {
                "DC No.": user_input.get("dc_no", ""),
                "Date": user_input.get("date", ""),
                "Customer / Project": user_input.get("customer_project", ""),
                "MCR No.": user_input.get("mcr_no", ""),
                "Product No.": user_input.get("product_no", ""),
                "Component No.": user_input.get("component_no", ""),
                "Initiator": user_input.get("initiator", ""),
            },
        },
        "change_description": {
            "title": "变更说明",
            "description": "展示变更原因、当前设计、变更方案和备注。",
            "data": {
                "Reason of Change": user_input.get("reason", ""),
                "Current Design": user_input.get("current_design", ""),
                "Change Proposal": user_input.get("change_proposal", ""),
                "Remarks": user_input.get("remarks", ""),
            },
        },
        "engineering_analysis": {
            "title": "工程分析与验证",
            "description": "展示 AI / RAG 生成的影响分析、风险分析、验证计划和相关检查项。",
            "data": {
                "Engineering Analysis": llm_result.get("engineering_analysis", ""),
                "Impact Analysis": llm_result.get("impact_analysis", ""),
                "Impact Description": llm_result.get("impact_description", ""),
                "Risk Analysis": llm_result.get("risk_analysis", ""),
                "Verification Plan": llm_result.get("verification_plan", ""),
                "Implementation Plan": llm_result.get("implementation_plan", ""),
                "Function / Performance": llm_result.get(
                    "function_performance_value", ""
                ),
                "Interface / Appearance": llm_result.get(
                    "interface_appearance_value", ""
                ),
                "Reliability / Robustness": llm_result.get(
                    "reliability_robustness_value", ""
                ),
                "Other Components": llm_result.get("other_components_value", ""),
                "Manufacturing / Assembly / Testing": llm_result.get(
                    "manufacturing_assembly_testing_value", ""
                ),
                "Supplier Part": llm_result.get("supplier_part_value", ""),
                "System / HW / SW / Calibration / Mechanical": llm_result.get(
                    "system_hw_sw_calibration_mechanical_value", ""
                ),
                "Trial Run": llm_result.get("trial_run_value", ""),
                "CMK": llm_result.get("capability_cmk_value", ""),
                "MSA": llm_result.get("capability_msa_value", ""),
                "MAE Release": llm_result.get("mae_release_value", ""),
                "Cleanness Test": llm_result.get("cleanness_test_value", ""),
                "QZ Test": llm_result.get("qz_test_value", ""),
                "PDL 200h": llm_result.get("pdl_200h_value", ""),
                "BOM Check": llm_result.get("bom_check_value", ""),
                "Test Report": llm_result.get("test_report_value", ""),
                "PAV Release": llm_result.get("pav_release_value", ""),
            },
        },
        "approval_signature": {
            "title": "签字与审批",
            "description": "展示历史案例推荐的负责人、确认人和审批签字人。",
            "data": {
                "Function Confirmed By": llm_result.get(
                    "function_performance_confirmed_by", ""
                ),
                "Interface Confirmed By": llm_result.get(
                    "interface_appearance_confirmed_by", ""
                ),
                "Reliability Confirmed By": llm_result.get(
                    "reliability_robustness_confirmed_by", ""
                ),
                "Manufacturing Confirmed By": llm_result.get(
                    "manufacturing_assembly_testing_confirmed_by", ""
                ),
                "Supplier Confirmed By": llm_result.get(
                    "supplier_part_confirmed_by", ""
                ),
                "Development Approver": llm_result.get(
                    "approval_development_person", ""
                ),
                "Purchasing Approver": llm_result.get("approval_purchasing_person", ""),
                "MFE Approver": llm_result.get("approval_mfe_person", ""),
                "COS Approver": llm_result.get("approval_cos_person", ""),
                "Quality Approver": llm_result.get("approval_quality_person", ""),
                "CPjM Approver": llm_result.get("approval_cpjm_person", ""),
                "MOEx Approver": llm_result.get("approval_moex_person", ""),
                "LOG Approver": llm_result.get("approval_log_person", ""),
                "Other Approver": llm_result.get("approval_other_person", ""),
                "Generated Report URL": report_url,
            },
        },
    }


def get_best_source_document(results: list) -> str:
    if not results:
        return ""

    best = results[0]

    metadata = best.get("metadata", {}) or {}

    return (
        metadata.get("document_name")
        or metadata.get("source")
        or metadata.get("_source")
        or ""
    )


def build_approval_search_input(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    专门增强 RAG 检索 Step 7 / Approval / 签字人表。
    原来的 user_input 主要是变更内容，不一定能召回报告末尾的签字人表。
    """
    approval_keywords = """
    Step 7 Implementation Approval
    Suggested Approvers
    导入清单
    签字人
    签字栏
    approval
    approver
    Development Purchasing MFE TEF COS Quality CPjM MOEx LOG
    研发 采购 工艺 样品 质量 客户项目 生产 物流
    TANG Liang TAO Jiong HE Yonggang XIA Qian SU Jian LUO Zhi XU Baochun
    """

    return {
        **user_input,
        "approval_search_keywords": approval_keywords,
    }


def read_template(filename: str) -> str:
    template_path = TEMPLATE_DIR / filename

    if not template_path.exists():
        raise FileNotFoundError(f"模板文件不存在：{template_path}")

    return template_path.read_text(encoding="utf-8")


# ============================================================
# LLM 结果缓存（相同输入 30 分钟内直接返回，避免重复调用大模型）
# ============================================================
_llm_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_LLM_CACHE_MAX_SIZE = 128
_LLM_CACHE_TTL_SECONDS = 1800  # 30 分钟


def _cache_key(user_input: Dict[str, Any]) -> str:
    """基于用户输入的稳定 hash 键。"""
    payload = json.dumps(user_input, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Dict[str, Any] | None:
    entry = _llm_cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if _time.time() - ts > _LLM_CACHE_TTL_SECONDS:
        _llm_cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    # 超过上限时淘汰最老的条目
    if len(_llm_cache) >= _LLM_CACHE_MAX_SIZE:
        oldest_key = min(_llm_cache, key=lambda k: _llm_cache[k][0])
        _llm_cache.pop(oldest_key, None)
    _llm_cache[key] = (_time.time(), value)


def _retrieve_approval_context(user_input: Dict[str, Any]) -> str:
    """Approval 兜底检索：用关键词增强查询，从历史案例中找签字人信息。"""
    approval_search_input = build_approval_search_input(user_input)
    approval_results = retrieve_pd_ecr_results(approval_search_input, top_k=20)
    approval_best_source = get_best_source_document_from_results(approval_results)
    debug_print("approval_best_source:", approval_best_source)
    return find_structured_signature_md(approval_best_source)


# ============================================================
# 动态审批周期估计：从历史案例中提取实际时间跨度
# ============================================================

def _parse_date_flexible(raw: str) -> str:
    """把 20251105 / 2025.11.05 / 2025-11-05 / 2025.11.7 统一成 YYYY-MM-DD。"""
    raw = str(raw or "").strip()
    # 20251105
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    # 2025.11.05 或 2025.11.7
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\b", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # 2025-11-05
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})\b", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _count_business_days(start_iso: str, end_iso: str) -> int:
    """计算两个 ISO 日期之间的工作日数。"""
    from datetime import date, timedelta

    try:
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
    except (ValueError, TypeError):
        return 0

    if end <= start:
        return 0

    days = 0
    current = start
    while current < end:
        if current.weekday() < 5:  # Mon=0 ... Fri=4
            days += 1
        current += timedelta(days=1)
    return days


def estimate_approval_lead_days(structured_text: str) -> int:
    """
    从历史 structured signature MD 中估计审批前置天数。

    优先级：
    1. 解析 initiation date → 最新 due_date 的时间差
    2. 统计需要签字的部门数量 → 5 + 部门数 × 2
    3. 兜底 12 个工作日
    """
    if not structured_text:
        return 12

    # —— 提取 initiation date ——
    init_date = ""
    date_patterns = [
        r"\bDate\s*[／/]?\s*日期\s*[:：]\s*(\d{8}|\d{4}[.-]\d{1,2}[.-]\d{1,2})",
        r"\bdate\s*[:：]\s*(\d{4}-\d{2}-\d{2})",
    ]
    for pat in date_patterns:
        m = re.search(pat, structured_text, re.I)
        if m:
            init_date = _parse_date_flexible(m.group(1))
            if init_date:
                break

    # —— 提取所有 due_date / plan_finish_date / implementation date ——
    due_dates = []
    due_patterns = [
        r"Due\s*date\s*[:：]?\s*(\d{8}|\d{4}[.-]\d{1,2}[.-]\d{1,2})",
        r"Plan\s*finish\s*date\s*[:：]?\s*(\d{8}|\d{4}[.-]\d{1,2}[.-]\d{1,2})",
        r"Planned?\s*implementation\s*date\s*[:：]?\s*(\d{8}|\d{4}[.-]\d{1,2}[.-]\d{1,2})",
    ]
    for pat in due_patterns:
        for m in re.finditer(pat, structured_text, re.I):
            parsed = _parse_date_flexible(m.group(1))
            if parsed:
                due_dates.append(parsed)

    # 方法 1：用历史日期跨度
    if init_date and due_dates:
        latest_due = max(due_dates)
        business_days = _count_business_days(init_date, latest_due)
        if business_days > 0:
            debug_print(
                f"历史案例周期：{init_date} → {latest_due} = {business_days} 工作日"
            )
            return min(business_days + 3, 30)  # 加 3 天缓冲，上限 30

    # 方法 2：统计签字部门数
    approval_fields = [
        "approval_development_person",
        "approval_purchasing_person",
        "approval_mfe_person",
        "approval_cos_person",
        "approval_quality_person",
        "approval_cpjm_person",
        "approval_moex_person",
        "approval_log_person",
        "approval_other_person",
    ]
    filled_count = 0
    for field in approval_fields:
        pat = rf"^{field}\s*[:：]\s*(\S.*)$"
        m = re.search(pat, structured_text, re.MULTILINE | re.I)
        if m and m.group(1).strip():
            filled_count += 1

    if filled_count > 0:
        lead = 5 + filled_count * 2
        debug_print(f"历史签字部门数: {filled_count}, 估计前置天数: {lead}")
        return min(lead, 25)

    # 方法 3：兜底
    debug_print("未能从历史案例提取审批周期，使用默认 12 工作日")
    return 12


@router.post("/generate-report")
async def generate_report(data: PdEcrInput):
    debug_print("========== 新版 generate_report 被调用 ==========")

    user_input = data.model_dump()
    debug_print("后端收到的数据：", user_input)

    # =========================
    # 0. 缓存检查——相同输入 30 分钟内秒返回
    # =========================
    cache_key = _cache_key(user_input)
    cached_result = _cache_get(cache_key)
    if cached_result is not None:
        debug_print("命中 LLM 缓存，直接返回")
        return cached_result

    # =========================
    # 1. RAG 检索（消除重复检索 + 并行化独立检索）
    # =========================
    try:
        # 1a. 主检索：只做一次 FAISS 搜索，上下文复用结果
        results_main = retrieve_pd_ecr_results(user_input, top_k=20)
        rag_context_main = retrieve_pd_ecr_context(
            user_input, top_k=20, results=results_main  # ← 关键优化：复用检索结果
        )

        best_source_document = get_best_source_document_from_results(results_main)
        structured_signature_context = find_structured_signature_md(
            best_source_document
        )

        # 1b. 并行执行两个独立检索：
        #   - affected_documents 检索（始终需要）
        #   - approval 兜底检索（仅当 structured md 未命中时需要）
        with ThreadPoolExecutor(max_workers=2) as executor:
            affected_future = executor.submit(
                retrieve_pd_ecr_context,
                build_affected_documents_search_input(user_input),
                10,
            )

            approval_future = None
            if not structured_signature_context:
                debug_print("主检索没有匹配到 structured md，并行触发 approval 检索兜底")
                approval_future = executor.submit(
                    _retrieve_approval_context,
                    user_input,
                )

            # 收集结果
            rag_context_affected_documents = affected_future.result()

            if approval_future:
                structured_signature_context = (
                    approval_future.result() or structured_signature_context
                )

        rag_context = (
            rag_context_main
            + "\n\n"
            + structured_signature_context
            + "\n\n"
            + rag_context_affected_documents
        )

        # 动态估算审批前置天数（从历史案例的日期跨度或签字部门数）
        approval_lead_days = estimate_approval_lead_days(
            structured_signature_context or rag_context_main
        )
        debug_print(f"动态审批前置天数: {approval_lead_days}")

        if DEBUG_PD_ECR:
            debug_print("========== RAG 主检索结果文件 ==========")
            debug_print("best_source_document:", best_source_document)
            debug_print("========== RAG 主检索内容 (前2000字符) ==========")
            debug_print(rag_context_main[:2000])
            debug_print("========== structured_signature_context ==========")
            debug_print(structured_signature_context[:500] if structured_signature_context else "(空)")
            debug_print("========== RAG Step 3.3 文档检查检索内容 (前500字符) ==========")
            debug_print(rag_context_affected_documents[:500])

    except Exception as e:
        debug_print("RAG 检索失败，将不使用历史知识库：", e)
        rag_context = ""
        structured_signature_context = ""

    # =========================
    # 2. 调用 LLM + 后处理
    # =========================
    try:
        raw_llm_result = await call_llm(user_input, rag_context)
        llm_result = extract_json_from_llm_result(raw_llm_result)

        debug_print("========== LLM 原始 JSON ==========")
        debug_print(json.dumps(llm_result, ensure_ascii=False, indent=2))

        # QA 表格兜底
        llm_result = normalize_quality_items_from_rag(llm_result, rag_context)

        # Step 3.3：优先从 structured md 读取
        llm_result = normalize_affected_documents_from_structured_rag(
            llm_result,
            structured_signature_context,
        )

        # Step 3.3：普通 RAG 兜底
        llm_result = normalize_affected_documents_from_rag(
            llm_result,
            rag_context,
        )

        debug_print("========== 结构化签字人抽取前 ==========")
        debug_print(
            json.dumps(
                {
                    "approval_development_person": llm_result.get(
                        "approval_development_person", ""
                    ),
                    "approval_purchasing_person": llm_result.get(
                        "approval_purchasing_person", ""
                    ),
                    "approval_mfe_person": llm_result.get("approval_mfe_person", ""),
                    "approval_cos_person": llm_result.get("approval_cos_person", ""),
                    "approval_quality_person": llm_result.get(
                        "approval_quality_person", ""
                    ),
                    "approval_cpjm_person": llm_result.get("approval_cpjm_person", ""),
                    "approval_moex_person": llm_result.get("approval_moex_person", ""),
                    "approval_log_person": llm_result.get("approval_log_person", ""),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        # Step 4 / Step 7：只从对应 structured md 读取实际签字人
        llm_result = extract_structured_actual_approval_from_rag(
            llm_result,
            structured_signature_context,
        )

        debug_print("========== 结构化签字人抽取后 ==========")
        debug_print(
            json.dumps(
                {
                    "approval_development_person": llm_result.get(
                        "approval_development_person", ""
                    ),
                    "approval_purchasing_person": llm_result.get(
                        "approval_purchasing_person", ""
                    ),
                    "approval_mfe_person": llm_result.get("approval_mfe_person", ""),
                    "approval_cos_person": llm_result.get("approval_cos_person", ""),
                    "approval_quality_person": llm_result.get(
                        "approval_quality_person", ""
                    ),
                    "approval_cpjm_person": llm_result.get("approval_cpjm_person", ""),
                    "approval_moex_person": llm_result.get("approval_moex_person", ""),
                    "approval_log_person": llm_result.get("approval_log_person", ""),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        # 清理非法 approval 值
        llm_result = clean_invalid_approval_persons(llm_result)

        debug_print("========== 清理非法签字人后 ==========")
        debug_print(
            json.dumps(
                {
                    "approval_development_person": llm_result.get(
                        "approval_development_person", ""
                    ),
                    "approval_purchasing_person": llm_result.get(
                        "approval_purchasing_person", ""
                    ),
                    "approval_mfe_person": llm_result.get("approval_mfe_person", ""),
                    "approval_cos_person": llm_result.get("approval_cos_person", ""),
                    "approval_quality_person": llm_result.get(
                        "approval_quality_person", ""
                    ),
                    "approval_cpjm_person": llm_result.get("approval_cpjm_person", ""),
                    "approval_moex_person": llm_result.get("approval_moex_person", ""),
                    "approval_log_person": llm_result.get("approval_log_person", ""),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        # 不再调用普通 approval 抽取，避免从 Signature Matrix 或其他案例误抽
        # llm_result = extract_approval_persons_from_rag(llm_result, rag_context)

        llm_result = clean_invalid_confirmed_by_persons(llm_result)

        llm_result = normalize_yes_no_fields(llm_result)
        llm_result = normalize_stock_boxes(llm_result)
        llm_result = apply_all_yes_no_boxes(llm_result)

        debug_print("========== 最终传给模板的结果 START ==========")
        debug_print(json.dumps(llm_result, ensure_ascii=False, indent=2))
        debug_print("========== 最终传给模板的结果 END ==========")

    except HTTPException:
        raise

    except Exception as e:
        debug_print("========== generate_report ERROR ==========")
        debug_print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"调用大模型失败：{str(e)}",
        )

    # =========================
    # 3. 组装模板上下文
    # =========================
    context = {
        **user_input,
        **llm_result,

        "basic_info": {
            "dc_no": user_input.get("dc_no", "") or llm_result.get("dc_no", ""),
            "date": user_input.get("date", "") or llm_result.get("date", ""),
            "customer_project": user_input.get("customer_project", "") or llm_result.get("customer_project", ""),
            "mcr_no": user_input.get("mcr_no", "") or llm_result.get("mcr_no", ""),
            "product_no": user_input.get("product_no", "") or llm_result.get("product_no", ""),
            "component_no": user_input.get("component_no", "") or llm_result.get("component_no", ""),
            "initiator": user_input.get("initiator", "") or llm_result.get("initiator", ""),
        },

        "change_request": {
            "reason": user_input.get("reason", "") or llm_result.get("reason", ""),
            "current_design": user_input.get("current_design", "") or llm_result.get("current_design", ""),
            "change_proposal": user_input.get("change_proposal", "") or llm_result.get("change_proposal", ""),
            "remarks": user_input.get("remarks", "") or llm_result.get("remarks", ""),
        },

        "change_reason": user_input.get("reason", "") or llm_result.get("change_reason", "") or llm_result.get("reason", ""),
        "current_design": user_input.get("current_design", "") or llm_result.get("current_design", ""),
        "change_proposal": user_input.get("change_proposal", "") or llm_result.get("change_proposal", ""),
        "remarks": user_input.get("remarks", "") or llm_result.get("remarks", ""),

        "now": llm_result.get("now", "") or user_input.get("current_design", ""),
        "after": llm_result.get("after", "") or user_input.get("change_proposal", ""),

        "engineering_analysis": llm_result.get("engineering_analysis", ""),
        "impact_analysis": llm_result.get("impact_analysis", ""),
        "impact_description": llm_result.get("impact_description", ""),
        "risk_analysis": llm_result.get("risk_analysis", ""),
        "verification_plan": llm_result.get("verification_plan", ""),
        "implementation_plan": llm_result.get("implementation_plan", ""),
        "affected_documents": llm_result.get("affected_documents", ""),
        "affected_actions": llm_result.get("affected_actions", ""),
        "execution_checklist": llm_result.get("execution_checklist", ""),
        "suggested_approvers": llm_result.get("suggested_approvers", []),
    }

    modules = []
    report_parts = []

    for module_id, meta in MODULE_TEMPLATE_MAP.items():
        template_file = meta["template_file"]
        module_content = render_template_file(template_file, context)

        modules.append(
            {
                "id": module_id,
                "title": meta["title"],
                "subtitle": template_file,
                "description": module_content[:200],
                "data": {
                    "template_file": template_file,
                    "content": module_content,
                },
            }
        )

        report_parts.append(module_content)

    report_markdown = "\n\n---\n\n".join(report_parts)

    dc_no = safe_filename(user_input.get("dc_no", ""))
    filename = f"report_{dc_no}.html"
    report_path = REPORTS_DIR / filename

    html_content = render_markdown_to_html_page(
        markdown_content=report_markdown,
        title=f"PD-ECR 工程变更报告 - {dc_no}",
    )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    report_url = f"/static/reports/{filename}"

    response = {
        "message": "生成成功",
        "url": report_url,
        "modules": modules,
        "llm_result": llm_result,
        "approval_lead_days": approval_lead_days,  # 从历史案例估算的审批前置天数
    }

    # 写入缓存（30 分钟 TTL）
    _cache_set(cache_key, response)

    return response


@router.post("/generate-draft")
async def generate_pd_ecr_draft(
    payload: PdEcrGenerateDraftPayload,
):
    try:
        similar_cases = payload.similar_cases
        if similar_cases is None:
            _, retrieved = retrieve_similar_cases(payload.input, top_k=5)
            similar_cases = [case.model_dump(mode="json") for case in retrieved]
        draft = generate_grounded_draft(payload.input, similar_cases=similar_cases)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PD-ECR draft generation failed: {e}")

    return draft.model_dump(mode="json")


@router.get("/drafts/{draft_id}/modules")
def get_pd_ecr_draft_modules(draft_id: str):
    draft = get_cached_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft not found: {draft_id}")

    return {
        "draft_id": draft.draft_id,
        "draft_status": draft.draft_status.value,
        "modules": [module.model_dump(mode="json") for module in draft.modules],
    }


@router.post("/export")
def export_pd_ecr_case(
    payload: PdEcrExportPayload,
):
    draft_id = payload.draft_id or (payload.draft or {}).get("draft_id")
    if not draft_id:
        raise HTTPException(status_code=422, detail="draft_id is required for V1 export")

    try:
        draft = get_cached_draft(str(draft_id))
        if draft is None and payload.draft:
            draft_payload = dict(payload.draft)
            cleaned_modules = []
            for module in draft_payload.get("modules") or []:
                if not isinstance(module, dict):
                    continue
                cleaned = dict(module)
                cleaned["module_id"] = cleaned.get("module_id") or cleaned.get("id")
                cleaned.pop("id", None)
                cleaned.pop("data", None)
                cleaned_modules.append(cleaned)
            draft_payload["modules"] = cleaned_modules
            draft = GeneratedDraft.model_validate(draft_payload)
        result = export_v1_draft(
            draft_id=str(draft_id),
            export_format="csv" if payload.format == "csv" else "html",
            draft=draft,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PD-ECR export failed: {e}")

    return result.model_dump(mode="json")


@router.get("/reports/{filename}")
def download_pd_ecr_v1_report(filename: str):
    safe_name = Path(filename).name
    report_path = REPORTS_DIR / safe_name
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="PD-ECR report not found")
    return FileResponse(report_path)


@router.post("/history/search")
@router.post("/test-rag")
def test_rag(data: PdEcrInput):
    user_input = data.model_dump()
    results = search_pdecr_pdf_case_records(user_input, top_k=20)
    approval_results: list[Dict[str, Any]] = []
    rag_context = "\n\n".join(
        json.dumps(result, ensure_ascii=False) for result in results
    )

    approval_test_result = {
        "approval_development_person": "",
        "approval_purchasing_person": "",
        "approval_mfe_person": "",
        "approval_cos_person": "",
        "approval_quality_person": "",
        "approval_cpjm_person": "",
        "approval_moex_person": "",
        "approval_log_person": "",
        "approval_other_person": "",
    }

    approval_test_result = extract_approval_persons_from_rag(
        approval_test_result,
        rag_context,
    )
    approval_test_result = clean_invalid_approval_persons(approval_test_result)

    approval_debug_lines = []
    for line in rag_context.splitlines():
        low = line.lower()
        if (
            "development" in low
            or "purchasing" in low
            or "quality" in low
            or "cpjm" in low
            or "moex" in low
            or "tang" in low
            or "tao" in low
            or "he yonggang" in low
            or "xia qian" in low
            or "su jian" in low
            or "luo zhi" in low
            or "xu baochun" in low
        ):
            approval_debug_lines.append(line)

    return {
        "message": "PDECR_JIE_JIM PDF metadata 检索成功",
        "query_input": user_input,
        "results_count": len(results),
        "approval_results_count": len(approval_results),
        "approval_test_result": approval_test_result,
        "approval_debug_lines": approval_debug_lines,
        "results": results,
        "case_rows": results,
        "related_cases": [
            result.get("case_id") or result.get("case_no") or result.get("id")
            for result in results
        ],
        "modules": modules_from_pdf_case_record(
            results[0],
            user_input,
            rag_records=results,
        )
        if results
        else [],
        "approval_results": approval_results,
        "rag_context": rag_context,
    }


@router.post("/test-structured-signature")
def test_structured_signature(data: PdEcrInput):
    user_input = data.model_dump()

    try:
        results_main = retrieve_pd_ecr_results(user_input, top_k=20)
        best_source_document = get_best_source_document_from_results(results_main)
        structured_signature_context = find_structured_signature_md(
            best_source_document
        )

        approval_test_result = {
            "approval_development_person": "",
            "approval_purchasing_person": "",
            "approval_mfe_person": "",
            "approval_cos_person": "",
            "approval_quality_person": "",
            "approval_cpjm_person": "",
            "approval_moex_person": "",
            "approval_log_person": "",
            "approval_other_person": "",
        }

        approval_after_extract = extract_structured_actual_approval_from_rag(
            approval_test_result.copy(),
            structured_signature_context,
        )

        approval_after_clean = clean_invalid_approval_persons(
            approval_after_extract.copy()
        )

        return {
            "message": "structured signature 测试完成",
            "query_input": user_input,
            "best_source_document": best_source_document,
            "structured_context_is_empty": not bool(structured_signature_context),
            "structured_context_preview": structured_signature_context[:3000],
            "approval_after_extract": approval_after_extract,
            "approval_after_clean": approval_after_clean,
        }

    except Exception as e:
        debug_print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"structured signature 测试失败：{str(e)}",
        )


# ============================================================
# 历史案例 MD → 模块内容提取
# ============================================================

# 每个模块对应的 Step 标题关键词（用于从历史 MD 中切分段落）
_HISTORICAL_MODULE_SECTION_MAP: dict[str, list[str]] = {
    "change-description": [
        "Step 1",
        "Step 2",
        "Change request",
        "Change proposal",
        "Basic information",
        "变更请求",
        "更改理由",
        "变更描述",
    ],
    "impact-analysis": [
        "Step 3.1",
        "Impact analysis",
        "影响分析",
        "Step 3.3",
        "Affected documents",
        "影响文档",
    ],
    "validation-plan": [
        "Step 3.2",
        "Quality Assurance",
        "验证计划",
        "Step 4",
        "Technical feasibility",
        "技术可行性",
        "Validation plan",
    ],
    "validation-result": [
        "Step 5",
        "Documents release",
        "文档发布",
        "Trial run result",
        "Validation result",
        "验证结果",
    ],
    "implementation-plan": [
        "Step 6.1",
        "Implementation check list",
        "导入清单",
        "Implementation task plan",
    ],
    "implementation-result": [
        "Step 6.2",
        "Implementation date",
        "执行日期",
        "Step 7",
        "Implementation Approval",
        "Approval",
        "签字",
    ],
}


def _strip_html(text: str) -> str:
    """去掉 HTML 标签，压缩空白。"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_historical_module_contents(source_text: str) -> dict[str, str]:
    """
    从历史案例原始文本（可能含 HTML）中按 Step 标题切分，
    返回 module_id → 对应文本 的映射。
    """
    clean = _strip_html(source_text)

    # 找所有 Step 标题的位置
    step_pattern = re.compile(
        r"(Step\s*\d+(?:\.\d+)?[:\s]*[^\n]{0,80})",
        re.IGNORECASE,
    )
    matches = list(step_pattern.finditer(clean))

    if not matches:
        # 没有 Step 标记，整段文本分配给 change-description
        return {"change-description": clean[:5000]}

    sections: dict[str, list[str]] = {key: [] for key in _HISTORICAL_MODULE_SECTION_MAP}

    for i, match in enumerate(matches):
        header = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(clean)
        body = clean[start:end].strip()

        # 按关键词匹配模块
        header_lower = header.lower()
        matched = False
        for module_id, keywords in _HISTORICAL_MODULE_SECTION_MAP.items():
            if any(kw.lower() in header_lower for kw in keywords):
                sections[module_id].append(body)
                matched = True
                break

        if not matched:
            # 兜底放进 change-description
            sections["change-description"].append(body)

    # 合并各模块文本，限制长度
    result: dict[str, str] = {}
    for module_id, parts in sections.items():
        merged = "\n\n".join(parts).strip()
        result[module_id] = merged[:6000] if merged else "（该历史案例未包含此部分内容）"

    return result


@router.get("/cases/modules")
def get_pd_ecr_case_modules(case_no: str):
    historical_case = find_historical_case(case_no)
    if historical_case:
        return {
            "message": "历史案例模块生成成功",
            "source": "history",
            "case": case_to_list_item(historical_case),
            "metadata": historical_case.metadata.model_dump(mode="json"),
            "missing_fields": historical_case.missing_fields,
            "modules": modules_from_historical_case(historical_case),
        }

    pdf_case = find_pdecr_pdf_case_record(case_no)
    if pdf_case:
        return {
            "message": "历史 PDF 案例模块生成成功",
            "source": "history",
            "case": pdf_case,
            "metadata": {},
            "missing_fields": [],
            "modules": modules_from_pdf_case_record(pdf_case),
        }

    # 1. 找到原始 MD 文件
    knowledge_dir = Path(__file__).resolve().parents[2] / "rag" / "knowledge"
    source_path = None

    requested = str(case_no or "").strip()
    requested_stem = Path(requested).stem
    requested_code = extract_case_code(requested)

    if knowledge_dir.exists():
        for path in sorted(knowledge_dir.glob("*.md")):
            if "_signature_structured" in path.stem:
                continue

            path_code = extract_case_code(path.name)
            if (
                requested == path.name
                or requested == path.stem
                or requested_stem == path.stem
                or (requested_code and requested_code == path_code)
            ):
                source_path = path
                break

    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"未找到案例：{case_no}（在 {knowledge_dir} 中没有匹配的 MD 文件）",
        )

    source_text = source_path.read_text(encoding="utf-8", errors="ignore")

    # 2. 提取结构化信息（metadata）
    case_record = build_knowledge_case_record(source_path, 0)

    # 3. 解析 parsed JSON 获取模块内容（如果有）
    parsed = load_parsed_case_json(source_path)
    parsed_modules = parsed.get("modules") if parsed else None

    # 4. 按 Step 提取各模块对应文本
    extracted = _extract_historical_module_contents(source_text)

    # 5. 构建模块列表
    modules = []
    for module_id, meta in MODULE_TEMPLATE_MAP.items():
        # 优先用 parsed JSON 的模块内容，其次用 MD 提取的段落
        parsed_key_map = {
            "change-description": "change_request_description",
            "impact-analysis": "impact_analysis",
            "validation-plan": "validation_trial_run_plan",
            "validation-result": "validation_trial_run_result",
            "implementation-plan": "implementation_task_plan",
            "implementation-result": "implementation_task_result",
        }
        parsed_key = parsed_key_map.get(module_id, "")
        parsed_content = (
            str(parsed_modules.get(parsed_key, "")).strip()
            if parsed_modules and parsed_key
            else ""
        )
        # 过滤掉占位符
        if parsed_content in ("", "...", "N/A", "None", "null"):
            parsed_content = ""

        raw_content = extracted.get(module_id, "")

        content = parsed_content or raw_content or "（未从历史案例中提取到此模块内容）"

        modules.append(
            {
                "id": module_id,
                "title": meta["title"],
                "subtitle": source_path.name,
                "description": _strip_html(content)[:200],
                "data": {
                    "source_file": source_path.name,
                    "content": content,
                },
            }
        )

    return {
        "message": "历史案例模块生成成功",
        "source": "history",
        "case": case_record,
        "modules": modules,
    }


@router.get("/cases/{case_id}")
def get_pd_ecr_case_detail(case_id: str, session: SessionDep):
    historical_case = find_historical_case(case_id)
    if historical_case:
        detail = case_to_detail(historical_case)
        detail["modules"] = modules_from_historical_case(historical_case)
        return detail

    pdf_case = find_pdecr_pdf_case_record(case_id)
    if pdf_case:
        return {
            "case": pdf_case,
            "modules": modules_from_pdf_case_record(pdf_case),
            "source": "history",
            "missing_fields": [],
        }

    case = get_case_or_404(session=session, case_id=case_id)
    return {
        "case": serialize_case(case),
        "modules": [
            serialize_module(module)
            for module in list_modules(session=session, case_id=case.id)
        ],
    }


@router.websocket("/cases/{case_id}/collaboration")
async def pd_ecr_case_collaboration(
    websocket: WebSocket,
    case_id: str,
    session_id: str = "",
    user_label: str = "Anonymous",
):
    try:
        parsed_case_id = uuid.UUID(case_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    session_id = session_id or hashlib.sha256(str(_time.time()).encode()).hexdigest()[:16]
    await pd_ecr_connection_manager.connect(
        case_id=parsed_case_id,
        websocket=websocket,
        session_id=session_id,
        user_label=user_label,
    )
    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "presence":
                await pd_ecr_connection_manager.update_presence(
                    case_id=parsed_case_id,
                    session_id=session_id,
                    module_id=message.get("module_id"),
                    field_path=message.get("field_path"),
                )
            elif message_type in {"patch", "saving", "saved", "conflict"}:
                await pd_ecr_connection_manager.broadcast(
                    case_id=parsed_case_id,
                    payload={
                        **message,
                        "session_id": session_id,
                        "user_label": user_label,
                    },
                )
    except WebSocketDisconnect:
        pd_ecr_connection_manager.disconnect(
            case_id=parsed_case_id,
            websocket=websocket,
            session_id=session_id,
        )
        await pd_ecr_connection_manager.broadcast_presence(case_id=parsed_case_id)
