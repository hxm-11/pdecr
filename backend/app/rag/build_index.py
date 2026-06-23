import os
import json
import pickle
import sys
from pathlib import Path
from typing import Any, List, Dict

import faiss
from sentence_transformers import SentenceTransformer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
JIE_JIM_DIR = BASE_DIR / "jie_jim_knowledge_pdf"
PDECR_PDF_DIR = BASE_DIR / "PDECR_JIE_JIM"
DOCLING_DIR = PDECR_PDF_DIR / "docling_output"
VECTOR_DIR = BASE_DIR / "vector_store"
MODEL_PATH = BASE_DIR / "models" / "paraphrase-multilingual-MiniLM-L12-v2"

VECTOR_DIR.mkdir(parents=True, exist_ok=True)

INDEX_PATH = VECTOR_DIR / "pd_ecr.faiss"
META_PATH = VECTOR_DIR / "pd_ecr_meta.pkl"


def read_text_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="gbk", errors="ignore")


def split_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = []

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def stringify_json_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return ", ".join(
            stringify_json_value(item)
            for item in value
            if stringify_json_value(item)
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

        for i, chunk in enumerate(split_text(stringify_json_value(module_text))):
            chunks.append({
                "source": source,
                "chunk_id": f"json_{module_name}_{i}",
                "document_type": "parsed_json",
                "case_id": case_id,
                "text": f"{module_header}{chunk}",
            })

    return chunks


def jie_jim_metadata_to_chunks() -> List[Dict]:
    """Load metadata.json from each jie_jim_knowledge_pdf subfolder into searchable chunks."""
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

        # Also index cleaned Markdown files if present
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
                for i, chunk in enumerate(split_text(text)):
                    chunks.append({
                        "source": metadata_path.parent.name,
                        "chunk_id": f"cleaned_{md_path.stem}_{i}",
                        "document_type": "jie_jim_cleaned",
                        "case_id": case_id,
                        "text": f"{header}{chunk}",
                    })

    return chunks


def docling_to_chunks() -> List[Dict]:
    """Load docling_output Markdown files into searchable chunks."""
    chunks: List[Dict] = []
    if not DOCLING_DIR.exists():
        print(f"docling_output 目录不存在: {DOCLING_DIR}")
        return chunks

    for md_path in sorted(DOCLING_DIR.glob("*_docling.md")):
        text = read_text_file(md_path)
        if not text.strip():
            continue

        # Extract case code from filename
        case_code = md_path.stem.replace("_docling", "")
        header = (
            f"Source file: docling_output/{md_path.name}\n"
            f"Document type: PD-ECR JIE/JIM docling parsed PDF\n"
            f"Case ID / 案例编号: {case_code}\n"
        )
        for i, chunk in enumerate(split_text(text)):
            chunks.append({
                "source": md_path.name,
                "chunk_id": f"docling_{i}",
                "document_type": "docling_pdf",
                "case_id": case_code,
                "text": f"{header}{chunk}",
            })

    return chunks


def load_documents() -> List[Dict]:
    docs: List[Dict] = []

    # 1. Knowledge directory (legacy MD/TXT files)
    if KNOWLEDGE_DIR.exists():
        for file_path in KNOWLEDGE_DIR.rglob("*"):
            if file_path.suffix.lower() not in [".txt", ".md"]:
                continue
            if "_signature_structured" in file_path.stem:
                continue
            text = read_text_file(file_path)
            for i, chunk in enumerate(split_text(text)):
                docs.append({
                    "source": file_path.name,
                    "chunk_id": i,
                    "document_type": "text",
                    "text": f"Source file: {file_path.name}\n{chunk}",
                })

        # Parsed JSON from knowledge/parsed/json/
        parsed_json_dir = KNOWLEDGE_DIR / "parsed" / "json"
        if parsed_json_dir.exists():
            for file_path in parsed_json_dir.glob("*.json"):
                docs.extend(parsed_json_to_chunks(file_path))

    # 2. JIE/JIM knowledge PDF metadata + cleaned Markdown
    docs.extend(jie_jim_metadata_to_chunks())

    # 3. Docling parsed PDF output
    docs.extend(docling_to_chunks())

    return docs


def main():
    docs = load_documents()

    if not docs:
        print("没有找到知识库文件，请把 .md/.txt 放到 app/rag/knowledge/，或把 .json 放到 app/rag/knowledge/parsed/json/")
        return

    print(f"共读取 {len(docs)} 个文本片段")

    if not MODEL_PATH.exists():
        raise RuntimeError(f"Local embedding model not found: {MODEL_PATH}")

    model = SentenceTransformer(str(MODEL_PATH))

    texts = [doc["text"] for doc in docs]
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, str(INDEX_PATH))

    with open(META_PATH, "wb") as f:
        pickle.dump(docs, f)

    print("RAG 索引构建完成")
    print("Index:", INDEX_PATH)
    print("Meta:", META_PATH)


if __name__ == "__main__":
    main()
