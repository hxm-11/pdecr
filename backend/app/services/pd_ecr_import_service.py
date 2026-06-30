import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models import (
    PD_ECR_DEFAULT_MODULES,
    HistoricalSourceDocument,
    PdEcrCase,
    PdEcrModule,
    User,
)
from app.services.pd_ecr_audit_service import write_activity
from app.services.pd_ecr_case_service import now_utc


APP_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = APP_DIR / "rag"
DATA_DIR = APP_DIR / "data"
KNOWLEDGE_DIR = RAG_DIR / "knowledge"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def safe_read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return value if isinstance(value, dict) else {"items": value}
    except Exception:
        return {}


def normalize_case_no(path: Path, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    for key in ("case_no", "case_id", "dc_no", "RequestNo", "request_no"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return sanitize_case_no(value)
    stem = re.sub(r"_docling$", "", path.stem, flags=re.I)
    stem = re.sub(r"_(model|content_list_v2|middle|origin)$", "", stem, flags=re.I)
    return sanitize_case_no(stem)


def sanitize_case_no(value: str) -> str:
    text = re.sub(r"\s+", "_", str(value).strip())
    text = text.strip("_-")
    return text or "PD-ECR-UNKNOWN"


def extract_metadata(
    path: Path,
    text: str,
    raw_json: dict[str, Any] | None = None,
    table_metadata: dict[str, str] | None = None,
    excel_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract structured metadata from parsed file content.

    Priority order (highest first):
    1. table_metadata  — MinerU markdown table parser (most reliable)
    2. excel_metadata  — Excel native key-value extraction
    3. raw_json        — pre-existing structured JSON (docling / metadata.json)
    4. text regex      — fallback patterns on raw markdown text
    """
    raw_json = raw_json or {}
    json_metadata = raw_json.get("metadata") if isinstance(raw_json.get("metadata"), dict) else {}
    json_business = raw_json.get("business_fields") if isinstance(raw_json.get("business_fields"), dict) else {}
    merged: dict[str, Any] = {
        **(table_metadata or {}),   # Tier 1: MinerU table parser
        **(excel_metadata or {}),    # Tier 2: Excel key-value
        **json_business,             # Tier 3: JSON business fields
        **json_metadata,             # Tier 3: JSON metadata
    }

    def first(keys: tuple[str, ...], patterns: tuple[str, ...] = ()) -> str | None:
        for key in keys:
            value = merged.get(key)
            if value not in (None, "", "N/A", "NA"):
                return str(value).strip()
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I | re.S)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip(" |:：")
                if value:
                    return value[:255]
        return None

    return {
        "case_no": normalize_case_no(path, merged),
        "title": path.parent.name if path.parent.name != "docling_output" else path.stem,
        "dc_no": first(("dc_no", "case_id"), (r"RequestNo\s*[:：]?\s*([A-Z0-9_\-]+)",)),
        "mcr_no": first(("mcr_no",), (r"MCR\s*(?:No\.?|#)?\s*[:：]?\s*([A-Z0-9_\-]+)",)),
        "customer_project": first(
            ("customer_project", "Customer_project_Name", "customer"),
            (r"Customer\s*project\s*Name[^：:]*[:：]\s*([^\n\r|]+)",),
        ),
        "product_no": first(("product_no", "affected_product_no", "product"), (r"Product\s*(?:No\.?|number)?\s*[:：]\s*([^\n\r|]+)",)),
        "part_no": first(("part_no", "component_no", "part_number"), (r"(?:Part|Component)\s*(?:No\.?|number)?\s*[:：]\s*([^\n\r|]+)",)),
        "change_type": first(("change_type", "type"), (r"Change\s*type\s*[:：]\s*([^\n\r|]+)",)),
        "sample_type": first(("sample_type",), (r"Sample\s*type\s*[:：]\s*([^\n\r|]+)",)),
        "initiator": first(("initiator", "responsible_person"), (r"Initiator[^：:]*[:：]\s*([^\n\r|]+)",)),
    }


def discover_historical_sources() -> list[Path]:
    candidates: list[Path] = []
    candidates.extend(sorted((RAG_DIR / "PDECR_JIE_JIM" / "docling_output").glob("*_docling.md")))
    candidates.extend(sorted((RAG_DIR / "PDECR_JIE_JIM" / "docling_output").glob("*_docling.json")))
    candidates.extend(sorted((RAG_DIR / "jie_jim_knowledge_pdf").glob("**/metadata.json")))
    candidates.extend(sorted((RAG_DIR / "jie_jim_knowledge_pdf").glob("**/ocr/*.json")))
    candidates.extend(sorted((RAG_DIR / "jie_jim_knowledge_pdf").glob("**/cleaned/*.md")))
    candidates.extend(sorted((DATA_DIR / "pd_ecr_cases").glob("*.json")))
    return [path for path in candidates if path.is_file()]


def source_kind(path: Path) -> str:
    name = path.name.lower()
    if name.endswith("_docling.md"):
        return "docling_markdown"
    if name.endswith("_docling.json"):
        return "docling_json"
    if path.name == "metadata.json":
        return "metadata_json"
    if path.suffix.lower() == ".json":
        return "ocr_json"
    if path.suffix.lower() == ".md":
        return "cleaned_markdown"
    return "unknown"


def _extract_pdecr_case_code(name: str) -> str:
    match = re.search(r"(PDECR\d{2}[_-]\d{3})", str(name or ""), re.I)
    if not match:
        return ""
    return match.group(1).upper().replace("-", "_")


def infer_display_pdf_path(path: Path, metadata: dict[str, Any] | None = None) -> Path | None:
    """Find the PDF users should see for a source file.

    The parsed Markdown/JSON can go to the knowledge base, but the UI should
    open this display PDF so historical cases keep their original layout.
    """
    if path.suffix.lower() == ".pdf" and path.exists():
        return path

    metadata = metadata or {}
    explicit_path = metadata.get("display_pdf_path") or metadata.get("preview_pdf_path")
    if explicit_path:
        candidate = Path(str(explicit_path))
        if candidate.suffix.lower() == ".pdf" and candidate.exists():
            return candidate

    requested_stems = {
        path.stem.lower(),
        str(metadata.get("case_no") or "").strip().lower(),
        str(metadata.get("dc_no") or "").strip().lower(),
    }
    requested_codes = {
        _extract_pdecr_case_code(path.name).lower(),
        _extract_pdecr_case_code(str(metadata.get("case_no") or "")).lower(),
        _extract_pdecr_case_code(str(metadata.get("dc_no") or "")).lower(),
    }
    requested_stems.discard("")
    requested_codes.discard("")

    for search_dir in (
        path.parent,
        APP_DIR / "uploads" / "previews",
        Path.cwd() / "uploads" / "previews",
        RAG_DIR / "PDECR_JIE_JIM",
        RAG_DIR / "jie_jim_knowledge_pdf",
    ):
        if not search_dir.exists():
            continue
        for pdf_path in sorted(search_dir.rglob("*.pdf")):
            pdf_stem = pdf_path.stem.lower()
            pdf_code = _extract_pdecr_case_code(pdf_path.name).lower()
            if pdf_stem in requested_stems or pdf_code in requested_codes:
                return pdf_path
            if any(stem and (pdf_stem.startswith(stem) or stem in pdf_stem) for stem in requested_stems):
                return pdf_path

    return None


def with_display_pdf_metadata(
    metadata: dict[str, Any],
    *,
    source_path: Path,
    display_pdf_path: Path | None,
    original_filename: str | None = None,
) -> dict[str, Any]:
    enriched = dict(metadata)
    enriched.setdefault("original_filename", original_filename or source_path.name)
    enriched.setdefault("original_file_path", str(source_path))
    if display_pdf_path:
        enriched["display_pdf_path"] = str(display_pdf_path)
        enriched["preview_pdf_path"] = str(display_pdf_path)
        enriched["pdf_file"] = display_pdf_path.name
    return enriched


def get_or_create_case(
    *,
    session: Session,
    metadata: dict[str, Any],
    source_type: str,
    current_user: User,
) -> PdEcrCase:
    case_no = sanitize_case_no(str(metadata.get("case_no") or "PD-ECR-UNKNOWN"))
    case = session.exec(select(PdEcrCase).where(PdEcrCase.case_no == case_no)).first()
    if case:
        return case

    case = PdEcrCase(
        case_no=case_no,
        title=str(metadata.get("title") or case_no)[:500],
        status="draft",
        source_type=source_type,
        is_historical=True,
        created_by_id=current_user.id,
        owner_id=current_user.id,
        dc_no=metadata.get("dc_no"),
        mcr_no=metadata.get("mcr_no"),
        customer_project=metadata.get("customer_project"),
        product_no=metadata.get("product_no"),
        part_no=metadata.get("part_no"),
        change_type=metadata.get("change_type"),
        sample_type=metadata.get("sample_type"),
        initiator=metadata.get("initiator"),
    )
    session.add(case)
    session.flush()
    ensure_import_modules(session=session, case=case, actor_id=current_user.id)
    write_activity(
        session=session,
        action="case.imported",
        case_id=case.id,
        actor_id=current_user.id,
        target_id=str(case.id),
        metadata={"source_type": source_type},
    )
    return case


def ensure_import_modules(
    *, session: Session, case: PdEcrCase, actor_id: uuid.UUID | None
) -> None:
    existing = set(
        session.exec(
            select(PdEcrModule.module_id).where(PdEcrModule.case_id == case.id)
        ).all()
    )
    for module_id, title in PD_ECR_DEFAULT_MODULES:
        if module_id in existing:
            continue
        session.add(
            PdEcrModule(
                case_id=case.id,
                module_id=module_id,
                title=title,
                content_json={},
                content_md="",
                source_cases=[case.case_no],
                source_files=[],
                status="imported" if case.is_historical else "draft",
                updated_by_id=actor_id,
            )
        )


def upsert_source_document(
    *,
    session: Session,
    case: PdEcrCase,
    path: Path,
    metadata: dict[str, Any],
    warnings: list[str],
    current_user: User,
) -> bool:
    digest = file_hash(path)
    display_pdf_path = infer_display_pdf_path(path, metadata)
    metadata = with_display_pdf_metadata(
        metadata,
        source_path=path,
        display_pdf_path=display_pdf_path,
    )
    existing = session.exec(
        select(HistoricalSourceDocument).where(
            HistoricalSourceDocument.source_path == str(path),
            HistoricalSourceDocument.content_hash == digest,
        )
    ).first()
    if existing:
        if existing.case_id is None:
            existing.case_id = case.id
        existing_metadata = dict(existing.extracted_metadata or {})
        changed = False
        for key, value in metadata.items():
            if value and not existing_metadata.get(key):
                existing_metadata[key] = value
                changed = True
        if changed:
            existing.extracted_metadata = existing_metadata
            session.add(existing)
        return False
    session.add(
        HistoricalSourceDocument(
            case_id=case.id,
            imported_by_id=current_user.id,
            source_file=path.name,
            source_path=str(path),
            source_kind=source_kind(path),
            content_hash=digest,
            extracted_metadata=metadata,
            import_warnings=warnings,
        )
    )
    return True


def merge_source_into_modules(
    *, session: Session, case: PdEcrCase, path: Path, text: str, metadata: dict[str, Any]
) -> None:
    modules = {
        module.module_id: module
        for module in session.exec(select(PdEcrModule).where(PdEcrModule.case_id == case.id)).all()
    }
    basic = modules.get("basic-information")
    if basic and not basic.content_json:
        basic.content_json = {key: value for key, value in metadata.items() if value}
        basic.source_files = sorted(set([*basic.source_files, path.name]))
    if text and path.suffix.lower() == ".md":
        target = modules.get("change-description")
        if target and not (target.content_md or "").strip():
            target.content_md = text[:20000]
            target.source_files = sorted(set([*target.source_files, path.name]))
            target.content_json = {"source_preview": text[:1000]}


def import_historical_sources(
    *, session: Session, current_user: User, limit: int | None = None
) -> dict[str, Any]:
    created_cases = 0
    updated_sources = 0
    skipped_sources = 0
    warnings_by_file: dict[str, list[str]] = {}

    sources = discover_historical_sources()
    if limit is not None:
        sources = sources[:limit]

    for path in sources:
        raw_json = safe_read_json(path) if path.suffix.lower() == ".json" else {}
        text = safe_read_text(path) if path.suffix.lower() == ".md" else json.dumps(raw_json, ensure_ascii=False)
        metadata = extract_metadata(path, text, raw_json)
        warnings: list[str] = []
        for field in ("case_no", "customer_project", "product_no", "part_no", "change_type"):
            if not metadata.get(field):
                warnings.append(f"missing_{field}")
        existing_case = session.exec(
            select(PdEcrCase).where(PdEcrCase.case_no == metadata["case_no"])
        ).first()
        case = get_or_create_case(
            session=session,
            metadata=metadata,
            source_type=source_kind(path),
            current_user=current_user,
        )
        if existing_case is None:
            created_cases += 1
        created_source = upsert_source_document(
            session=session,
            case=case,
            path=path,
            metadata=metadata,
            warnings=warnings,
            current_user=current_user,
        )
        if created_source:
            updated_sources += 1
        else:
            skipped_sources += 1
        merge_source_into_modules(session=session, case=case, path=path, text=text, metadata=metadata)
        if warnings:
            warnings_by_file[path.name] = warnings

    write_activity(
        session=session,
        action="historical_import.completed",
        actor_id=current_user.id,
        target_type="import",
        metadata={
            "sources_seen": len(sources),
            "created_cases": created_cases,
            "updated_sources": updated_sources,
            "skipped_sources": skipped_sources,
        },
    )
    session.commit()
    return {
        "sources_seen": len(sources),
        "created_cases": created_cases,
        "updated_sources": updated_sources,
        "skipped_sources": skipped_sources,
        "warnings_by_file": warnings_by_file,
    }


def ingest_uploaded_file(
    *,
    session: Session,
    file_path: Path,
    original_filename: str,
    current_user: User,
) -> dict[str, Any]:
    """Parse an uploaded Excel or PDF file, create a PdEcrCase, and return parsed data.

    Enhanced pipeline:
    - PDF:  MinerU → structured table metadata + keyword-filtered markdown
    - Excel: openpyxl/xlrd → keyword-filtered markdown
             then optionally Excel→PDF→MinerU for richer indexing
    """
    import shutil
    import traceback

    from app.core.config import settings
    from app.rag.excel_to_markdown import convert_excel as _convert_excel
    from app.rag.pdf_to_markdown import convert_pdf as _convert_pdf
    from app.rag.mineru_md_parser import extract_structured_metadata

    suffix = file_path.suffix.lower()
    knowledge_md_path: Path | None = None
    parsed_text = ""
    parsed_by = ""
    table_metadata: dict[str, str] = {}
    excel_metadata: dict[str, str] = {}
    display_pdf_path: Path | None = file_path if suffix == ".pdf" else None

    # ---- Parse file ----
    if suffix in (".xlsx", ".xlsm", ".xls"):
        # ── Excel path ──
        _convert_excel(file_path)
        knowledge_md_path = KNOWLEDGE_DIR / f"{file_path.stem}.md"
        parsed_by = "excel_to_markdown"

        # ── Enhanced: Excel → PDF → MinerU for richer knowledge base content ──
        try:
            from app.rag.excel_to_pdf import convert_excel_to_pdf
            pdf_path = convert_excel_to_pdf(file_path)
            if pdf_path:
                display_pdf_path = pdf_path
            if pdf_path and shutil.which("mineru") is not None:
                from app.rag.pdf_to_markdown import run_mineru, write_pdf_markdown
                mineru_md_path = run_mineru(pdf_path, backend="pipeline")
                mineru_text = mineru_md_path.read_text(encoding="utf-8", errors="ignore")

                # Write MinerU markdown to knowledge/ for FAISS indexing
                mineru_knowledge_path = KNOWLEDGE_DIR / f"{file_path.stem}_mineru.md"
                write_pdf_markdown(
                    file_path,
                    f"Excel→PDF→MinerU ({original_filename})",
                    mineru_text,
                )
                # Overwrite the default output path with our preferred location
                default_out = KNOWLEDGE_DIR / f"{file_path.stem}.md"
                if mineru_knowledge_path.exists() and mineru_knowledge_path != default_out:
                    # write_pdf_markdown writes to KNOWLEDGE_DIR/{stem}.md;
                    # rename to _mineru.md so the original keyword-filtered
                    # markdown is preserved
                    if default_out.exists():
                        default_out.replace(mineru_knowledge_path)

                # Extract structured table metadata from MinerU markdown
                table_metadata = extract_structured_metadata(mineru_text)
        except Exception:
            traceback.print_exc()
            # Non-fatal: Excel→PDF→Mineru is an enhancement

    elif suffix == ".pdf":
        # ── PDF path ──
        _convert_pdf(file_path)
        knowledge_md_path = KNOWLEDGE_DIR / f"{file_path.stem}.md"
        parsed_by = "pdf_to_markdown"

        # ── Enhanced: extract structured table metadata from MinerU output ──
        if knowledge_md_path and knowledge_md_path.exists():
            parsed_text = safe_read_text(knowledge_md_path)
            try:
                table_metadata = extract_structured_metadata(parsed_text)
            except Exception:
                traceback.print_exc()
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    if knowledge_md_path and knowledge_md_path.exists():
        parsed_text = safe_read_text(knowledge_md_path)

    # ---- Extract metadata (table_metadata has highest priority) ----
    metadata = extract_metadata(
        file_path,
        parsed_text,
        table_metadata=table_metadata,
        excel_metadata=excel_metadata,
    )
    metadata = with_display_pdf_metadata(
        metadata,
        source_path=file_path,
        display_pdf_path=display_pdf_path,
        original_filename=original_filename,
    )
    case_no = metadata["case_no"]

    # ---- Create or get case ----
    existing_case = session.exec(
        select(PdEcrCase).where(PdEcrCase.case_no == case_no)
    ).first()
    case = get_or_create_case(
        session=session,
        metadata=metadata,
        source_type="file_upload",
        current_user=current_user,
    )
    is_new = existing_case is None

    # ---- Save source document record ----
    upsert_source_document(
        session=session,
        case=case,
        path=file_path,
        metadata=metadata,
        warnings=[],
        current_user=current_user,
    )

    # ---- Fill module content from parsed text ----
    merge_source_into_modules(
        session=session,
        case=case,
        path=knowledge_md_path or file_path,
        text=parsed_text,
        metadata=metadata,
    )

    write_activity(
        session=session,
        action="case.file_uploaded",
        case_id=case.id,
        actor_id=current_user.id,
        target_id=str(case.id),
        metadata={
            "original_filename": original_filename,
            "parsed_by": parsed_by,
            "is_new_case": is_new,
        },
    )
    session.commit()

    return {
        "case_id": str(case.id),
        "case_no": case_no,
        "is_new": is_new,
        "parsed_by": parsed_by,
        "metadata": metadata,
        "content_preview": parsed_text[:2000],
    }
