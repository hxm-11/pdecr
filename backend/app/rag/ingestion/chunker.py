"""按业务模块切 chunk（不做固定长度全文硬切）。

每个非空业务模块 -> 一个 chunk；tasks 逐条成 chunk；basic_info 由元数据拼成
一个 chunk。超长模块再用 RecursiveCharacterTextSplitter 二次细分，但仍带同一
chunk_type，保证"按模块检索"的语义。

每个 chunk 都携带完整 metadata，支持按
case_id / dc_no / mcr_no / customer_project / affected_product_no /
component_no / source_file / file_type / chunk_type 过滤。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.rag.schemas.pdecr_case_schema import PdecrCase

# 超过此长度的模块正文会二次细分
_MAX_CHUNK_CHARS = 1200

# 模块字段 -> chunk_type（与 schema.MODULE_NAMES 对齐，remarks 归到 basic 备注不单列）
_MODULE_CHUNK_TYPES = [
    ("change_reason", "change_reason"),
    ("current_design", "current_design"),
    ("change_proposal", "change_proposal"),
    ("impact_analysis", "impact_analysis"),
    ("validation_plan", "validation_plan"),
    ("implementation_plan", "implementation_plan"),
    ("risk_analysis", "risk_analysis"),
    ("approval_summary", "approval_summary"),
]


@dataclass
class Chunk:
    chunk_id: str
    case_id: str
    chunk_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "case_id": self.case_id,
            "chunk_type": self.chunk_type,
            "text": self.text,
            "metadata": self.metadata,
        }


def _base_metadata(case: PdecrCase) -> dict[str, Any]:
    md = case.metadata
    return {
        "case_id": case.case_id,
        "dc_no": md.dc_no,
        "mcr_no": md.mcr_no,
        "customer_project": md.customer_project,
        "affected_product_no": md.affected_product_no,
        "component_no": md.component_no,
        "source_file": case.source.source_file,
        "file_type": case.source.file_type,
    }


def _split_long(text: str) -> list[str]:
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text]
    try:
        from app.rag.ingest.chunk import chunk_text

        parts = chunk_text(text)
        return parts or [text]
    except Exception:
        # 无 langchain 时的朴素兜底：按段落聚合到阈值
        parts, buf = [], ""
        for para in text.split("\n\n"):
            if len(buf) + len(para) > _MAX_CHUNK_CHARS and buf:
                parts.append(buf.strip())
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            parts.append(buf.strip())
        return parts or [text]


def build_chunks(case: PdecrCase, markdown: str | None = None) -> list[Chunk]:  # noqa: ARG001
    """基于业务模块生成 chunks。

    markdown 参数按需求保留（chunker 输入为 PdecrCase + 标准 Markdown），当前实现
    直接从结构化 case 切分，更稳定；markdown 供未来按渲染文本对齐时使用。
    """
    chunks: list[Chunk] = []
    base = _base_metadata(case)

    # ── basic_info ──
    md = case.metadata
    basic_lines = [
        f"Case ID: {case.case_id}",
        f"DC No: {md.dc_no or ''}",
        f"Date: {md.date or ''}",
        f"MCR No: {md.mcr_no or ''}",
        f"Customer Project: {', '.join(md.customer_project)}",
        f"Affected Product No: {', '.join(md.affected_product_no)}",
        f"Component No: {', '.join(md.component_no)}",
        f"Initiator: {md.initiator or ''}",
        f"Department: {md.department or ''}",
        f"Product Family: {md.product_family or ''}",
        f"Change Type: {md.change_type or ''}",
    ]
    chunks.append(
        Chunk(
            chunk_id=f"{case.case_id}::basic_info",
            case_id=case.case_id,
            chunk_type="basic_info",
            text="\n".join(basic_lines),
            metadata={**base, "chunk_type": "basic_info"},
        )
    )

    # ── 业务模块 ──
    for field_name, chunk_type in _MODULE_CHUNK_TYPES:
        content = getattr(case.modules, field_name)
        if not content or not content.strip():
            continue
        parts = _split_long(content.strip())
        for i, part in enumerate(parts):
            suffix = f"::{chunk_type}" + (f"_{i}" if len(parts) > 1 else "")
            chunks.append(
                Chunk(
                    chunk_id=f"{case.case_id}{suffix}",
                    case_id=case.case_id,
                    chunk_type=chunk_type,
                    text=part,
                    metadata={**base, "chunk_type": chunk_type},
                )
            )

    # ── tasks（逐条）──
    for idx, task in enumerate(case.tasks):
        pieces = [
            task.task_name,
            f"Owner: {task.owner}" if task.owner else None,
            f"Department: {task.department}" if task.department else None,
            f"Plan: {task.plan}" if task.plan else None,
            f"Result: {task.result}" if task.result else None,
            f"Status: {task.status}" if task.status else None,
        ]
        text = "\n".join(p for p in pieces if p)
        if not text.strip():
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{case.case_id}::task_{idx}",
                case_id=case.case_id,
                chunk_type="task",
                text=text,
                metadata={**base, "chunk_type": "task"},
            )
        )

    return chunks
