"""文档读取：把各类源文件读成统一的 chunk 列表。

产出格式与旧 build_index 完全一致（键：source / chunk_id / document_type /
case_id / text），因此检索层和 graph 层无需改动。

与旧版唯一的区别：切分改用 ingest.chunk.chunk_text（RecursiveCharacterTextSplitter）。

源目录：
  1. knowledge/                    —— 遗留 md/txt + parsed/json 结构化案例
  2. jie_jim_knowledge_pdf/*/      —— metadata.json + cleaned/*.md
  3. PDECR_JIE_JIM/docling_output/ —— *_docling.md
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from .chunk import chunk_text

BASE_DIR = Path(__file__).resolve().parent.parent  # app/rag
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_BASE_CHUNKS_PATH = BASE_DIR / "knowledge_base" / "chunks" / "chunks.jsonl"
JIE_JIM_DIR = BASE_DIR / "jie_jim_knowledge_pdf"
PDECR_PDF_DIR = BASE_DIR / "PDECR_JIE_JIM"
DOCLING_DIR = PDECR_PDF_DIR / "docling_output"


def read_text_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="gbk", errors="ignore")


# ── JSON 值格式化辅助（沿用旧逻辑）──
def stringify_json_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(
            stringify_json_value(item) for item in value if stringify_json_value(item)
        )
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip()


def add_json_field(lines: List[str], label: str, value: Any) -> None:
    text = stringify_json_value(value)
    if text:
        lines.append(f"{label}: {text}")


def is_placeholder_text(value: Any) -> bool:
    text = stringify_json_value(value).strip().lower()
    return text in {"", "...", "n/a", "na", "none", "-", "null"}


# ── 1. knowledge/parsed/json 结构化案例 ──
def parsed_json_to_chunks(file_path: Path) -> List[Dict]:
    try:
        data = json.loads(read_text_file(file_path))
    except json.JSONDecodeError as exc:
        print(f"跳过无法解析的 JSON: {file_path} ({exc})")
        return []

    metadata = data.get("metadata") or {}
    business_fields = data.get("business_fields") or {}
    modules = data.get("modules") or {}

    source = file_path.name
    case_id = data.get("case_id") or file_path.stem.replace(" copy", "")

    base_lines = [
        f"Source file: {source}",
        "Document type: structured PD-ECR parsed JSON",
        "文档类型: 结构化 PD-ECR JSON",
    ]
    add_json_field(base_lines, "Case ID / 案例编号", case_id)
    add_json_field(base_lines, "Original source file / 原始文件", data.get("source_file"))
    add_json_field(base_lines, "DC No / 开发更改编号", metadata.get("dc_no"))
    add_json_field(base_lines, "Date / 日期", metadata.get("date"))
    add_json_field(base_lines, "MCR No / MCR号", metadata.get("mcr_no"))
    add_json_field(base_lines, "Customer project / 客户项目", metadata.get("customer_project"))
    add_json_field(base_lines, "Affected product no / 影响产品号", metadata.get("affected_product_no"))
    add_json_field(base_lines, "Component no / 零部件号", metadata.get("component_no"))
    add_json_field(base_lines, "Sample type / 样品类型", metadata.get("sample_type"))
    add_json_field(base_lines, "Change type / 更改类型", metadata.get("change_type"))
    add_json_field(base_lines, "Change type raw / 更改类型原文", metadata.get("change_type_raw"))
    add_json_field(base_lines, "Source type / 来源类型", metadata.get("source_type"))
    add_json_field(base_lines, "Language / 语言", metadata.get("language"))
    add_json_field(base_lines, "Requires validation / 是否需要验证", metadata.get("requires_validation"))
    add_json_field(base_lines, "Responsible person / 负责人", business_fields.get("responsible_person"))
    add_json_field(base_lines, "Responsible department / 负责部门", business_fields.get("responsible_department"))
    add_json_field(base_lines, "Approval persons / 审批人员", business_fields.get("approval_persons"))
    add_json_field(base_lines, "Approval departments / 审批部门", business_fields.get("approval_departments"))
    add_json_field(base_lines, "Affected documents / 影响文档", business_fields.get("affected_documents"))

    chunks = [{
        "source": source,
        "chunk_id": "json_metadata",
        "document_type": "parsed_json",
        "case_id": case_id,
        "text": "\n".join(base_lines),
    }]

    for module_name, module_text in modules.items():
        if is_placeholder_text(module_text):
            continue

        module_header = (
            f"Source file: {source}\n"
            "Document type: structured PD-ECR parsed JSON module\n"
            f"Case ID / 案例编号: {case_id}\n"
            f"Module / 模块: {module_name}\n"
        )
        for i, chunk in enumerate(chunk_text(stringify_json_value(module_text))):
            chunks.append({
                "source": source,
                "chunk_id": f"json_{module_name}_{i}",
                "document_type": "parsed_json",
                "case_id": case_id,
                "text": f"{module_header}{chunk}",
            })

    return chunks


# ── 2. jie_jim_knowledge_pdf 元数据 + cleaned markdown ──
def jie_jim_metadata_to_chunks() -> List[Dict]:
    chunks: List[Dict] = []
    if not JIE_JIM_DIR.exists():
        print(f"jie_jim_knowledge_pdf 目录不存在: {JIE_JIM_DIR}")
        return chunks

    for metadata_path in sorted(JIE_JIM_DIR.glob("*/metadata.json")):
        try:
            record = json.loads(read_text_file(metadata_path))
        except json.JSONDecodeError as exc:
            print(f"跳过无法解析的 metadata: {metadata_path} ({exc})")
            continue

        case_id = record.get("case_id") or metadata_path.parent.name
        metadata = record.get("metadata") or {}
        change_basic = record.get("change_basic") or {}

        lines = [
            f"Source file: {metadata_path.parent.name}/metadata.json",
            "Document type: PD-ECR JIE/JIM metadata",
            "文档类型: PD-ECR JIE/JIM 元数据",
        ]
        add_json_field(lines, "Case ID / 案例编号", case_id)
        add_json_field(lines, "DC No / 开发更改编号", metadata.get("dc_no"))
        add_json_field(lines, "Date / 日期", metadata.get("date"))
        add_json_field(lines, "Customer project / 客户项目", metadata.get("customer_project"))
        add_json_field(lines, "MCR No / MCR号", metadata.get("mcr_no"))
        add_json_field(lines, "Sample status / 样品状态", metadata.get("sample_status"))
        add_json_field(lines, "Sample type / 样品类型", metadata.get("sample_type"))
        add_json_field(lines, "Change type / 更改类型", metadata.get("change_type"))
        add_json_field(lines, "Change source / 更改来源", change_basic.get("change_source"))
        add_json_field(lines, "Change part / 变更零件", change_basic.get("change_part_product_name"))
        add_json_field(lines, "Reason for change / 变更原因", change_basic.get("reason_for_change"))
        add_json_field(lines, "Original source / 原始文件", record.get("source_file"))

        chunks.append({
            "source": metadata_path.parent.name,
            "chunk_id": "metadata",
            "document_type": "jie_jim_metadata",
            "case_id": case_id,
            "text": "\n".join(lines),
        })

        cleaned_dir = metadata_path.parent / "cleaned"
        if cleaned_dir.exists():
            for md_path in sorted(cleaned_dir.glob("*.md")):
                text = read_text_file(md_path)
                if not text.strip():
                    continue
                header = (
                    f"Source file: {metadata_path.parent.name}/cleaned/{md_path.name}\n"
                    f"Document type: PD-ECR JIE/JIM cleaned Markdown\n"
                    f"Case ID / 案例编号: {case_id}\n"
                )
                for i, chunk in enumerate(chunk_text(text)):
                    chunks.append({
                        "source": metadata_path.parent.name,
                        "chunk_id": f"cleaned_{md_path.stem}_{i}",
                        "document_type": "jie_jim_cleaned",
                        "case_id": case_id,
                        "text": f"{header}{chunk}",
                    })

    return chunks


# ── 3. docling 解析的 PDF markdown ──
def docling_to_chunks() -> List[Dict]:
    chunks: List[Dict] = []
    if not DOCLING_DIR.exists():
        print(f"docling_output 目录不存在: {DOCLING_DIR}")
        return chunks

    for md_path in sorted(DOCLING_DIR.glob("*_docling.md")):
        text = read_text_file(md_path)
        if not text.strip():
            continue

        case_code = md_path.stem.replace("_docling", "")
        header = (
            f"Source file: docling_output/{md_path.name}\n"
            f"Document type: PD-ECR JIE/JIM docling parsed PDF\n"
            f"Case ID / 案例编号: {case_code}\n"
        )
        for i, chunk in enumerate(chunk_text(text)):
            chunks.append({
                "source": md_path.name,
                "chunk_id": f"docling_{i}",
                "document_type": "docling_pdf",
                "case_id": case_code,
                "text": f"{header}{chunk}",
            })

    return chunks


# ── 4. 新 ingestion pipeline 产出的标准化 chunks.jsonl ──
def knowledge_base_jsonl_to_chunks() -> List[Dict]:
    """读取 app/rag/knowledge_base/chunks/chunks.jsonl，接入主 FAISS 索引。

    新的 ingestion pipeline 会先把案例标准化成 PdecrCase，再按业务模块写
    chunks.jsonl。主检索层仍然基于 vector_store/langchain_faiss，因此这里把
    JSONL chunk 转成 build_index 期望的统一格式，避免"入库了但检索不到"。
    """
    chunks: List[Dict] = []
    if not KNOWLEDGE_BASE_CHUNKS_PATH.exists():
        return chunks

    for line_no, line in enumerate(
        KNOWLEDGE_BASE_CHUNKS_PATH.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                f"跳过无法解析的 knowledge_base chunk: "
                f"{KNOWLEDGE_BASE_CHUNKS_PATH}:{line_no} ({exc})"
            )
            continue

        text = str(row.get("text") or "").strip()
        if not text:
            continue

        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        case_id = str(row.get("case_id") or metadata.get("case_id") or "").strip()
        chunk_type = str(
            row.get("chunk_type") or metadata.get("chunk_type") or "module"
        ).strip()
        chunk_id = str(
            row.get("chunk_id") or f"{case_id or 'knowledge_base'}::{line_no}"
        )
        source = str(
            metadata.get("source_file")
            or metadata.get("source")
            or case_id
            or KNOWLEDGE_BASE_CHUNKS_PATH.name
        )

        header = (
            f"Source file: {source}\n"
            "Document type: standardized PD-ECR knowledge base chunk\n"
            f"Case ID / 案例编号: {case_id}\n"
            f"Module / 模块: {chunk_type}\n"
        )
        chunks.append(
            {
                "source": source,
                "chunk_id": chunk_id,
                "document_type": "knowledge_base_chunk",
                "case_id": case_id,
                "chunk_type": chunk_type,
                "metadata": metadata,
                "text": f"{header}{text}",
            }
        )

    return chunks


# ── 内容级去重（同一篇文档被多个 hash 目录重复 ingest 的问题）──
# 剥掉携带文件名/hash/编号的易变行后，按真实正文判重；
# 保留其余字段（customer_project / 模块正文等），避免把不同案例误判为重复。
_VOLATILE_LINE_PREFIXES = (
    "Source file:",
    "Case ID",           # "Case ID / 案例编号: ..."
    "Original source",   # "Original source file / 原始文件: ..."
)


def _content_key(text: str) -> str:
    kept: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(p) for p in _VOLATILE_LINE_PREFIXES):
            continue
        kept.append(stripped)
    norm = "\n".join(kept)
    return hashlib.md5(norm.encode("utf-8")).hexdigest()


def dedup_documents(docs: List[Dict]) -> List[Dict]:
    """按正文内容去重，保留首次出现的片段。"""
    seen: set[str] = set()
    out: List[Dict] = []
    dropped = 0
    for doc in docs:
        key = _content_key(doc.get("text", ""))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(doc)
    if dropped:
        print(f"[parse] 内容去重：移除 {dropped} 个重复片段，保留 {len(out)} 个（原 {len(docs)}）")
    return out


def load_documents() -> List[Dict]:
    """读取全部源，返回统一的 chunk 列表（已按内容去重）。"""
    docs: List[Dict] = []

    if KNOWLEDGE_DIR.exists():
        for file_path in KNOWLEDGE_DIR.rglob("*"):
            if file_path.suffix.lower() not in [".txt", ".md"]:
                continue
            if "_signature_structured" in file_path.stem:
                continue

            stem = file_path.stem.lower()
            if "_mineru" in stem:
                doc_type = "excel_via_mineru"
            elif stem.endswith("_parsed"):
                doc_type = "excel_keyword_filtered"
            else:
                doc_type = "text"

            text = read_text_file(file_path)
            for i, chunk in enumerate(chunk_text(text)):
                docs.append({
                    "source": file_path.name,
                    "chunk_id": i,
                    "document_type": doc_type,
                    "text": f"Source file: {file_path.name}\n{chunk}",
                })

        parsed_json_dir = KNOWLEDGE_DIR / "parsed" / "json"
        if parsed_json_dir.exists():
            for file_path in parsed_json_dir.glob("*.json"):
                docs.extend(parsed_json_to_chunks(file_path))

    docs.extend(jie_jim_metadata_to_chunks())
    docs.extend(docling_to_chunks())
    docs.extend(knowledge_base_jsonl_to_chunks())

    return dedup_documents(docs)
