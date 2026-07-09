"""基于 LLM 的 PD-ECR 抽取器。

输入 ParsedDocument，按 prompts/pdecr_extract_prompt.md 让 LLM 结构化输出
PdecrCase 的 metadata + modules。抽不到的字段必须为空，不得编造。

LLM 未配置（无 LLM_API_KEY）或调用失败时，自动回退到 RuleBasedExtractor，
保证 pipeline 不中断。对外统一用 get_extractor() 拿一个可用抽取器。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.rag.schemas.pdecr_case_schema import (
    PdecrCase,
    PdecrMetadata,
    PdecrModules,
    QualityControl,
    SourceInfo,
)

from ..loaders import ParsedDocument
from .rule_based_extractor import RuleBasedExtractor

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "pdecr_extract_prompt.md"
)

# 送给 LLM 的正文上限，避免超长（前置内容通常已含关键信息）
_MAX_CHARS = int(os.getenv("PDECR_EXTRACT_MAX_CHARS", "24000"))


# ── LLM 结构化输出 schema（只让它填能从原文读到的字段）──
class _LlmMetadata(BaseModel):
    dc_no: str | None = None
    date: str | None = None
    mcr_no: str | None = None
    customer_project: list[str] = Field(default_factory=list)
    affected_product_no: list[str] = Field(default_factory=list)
    component_no: list[str] = Field(default_factory=list)
    initiator: str | None = None
    department: str | None = None
    product_family: str | None = None
    change_type: str | None = None


class _LlmExtraction(BaseModel):
    metadata: _LlmMetadata = Field(default_factory=_LlmMetadata)
    change_reason: str | None = None
    current_design: str | None = None
    change_proposal: str | None = None
    impact_analysis: str | None = None
    validation_plan: str | None = None
    implementation_plan: str | None = None
    risk_analysis: str | None = None
    approval_summary: str | None = None
    remarks: str | None = None


def llm_available() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


class LlmExtractor:
    extractor_name = "llm"

    def __init__(self, fallback: Any | None = None) -> None:
        self._fallback = fallback or RuleBasedExtractor()

    def extract(self, parsed: ParsedDocument) -> PdecrCase:
        if not llm_available():
            return self._fallback.extract(parsed)
        try:
            return self._extract_with_llm(parsed)
        except Exception as exc:  # 网络/额度/解析失败 → 回退，不中断入库
            case = self._fallback.extract(parsed)
            case.quality_control.errors.append(f"LLM extract failed, fell back: {exc}")
            return case

    # ── 内部 ──────────────────────────────────────────────
    def _extract_with_llm(self, parsed: ParsedDocument) -> PdecrCase:
        from app.rag.graph.llm import get_chat_model

        prompt = (
            _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""
        )
        content = parsed.full_text()[:_MAX_CHARS]

        model = get_chat_model(temperature=0.0).with_structured_output(_LlmExtraction)
        result: _LlmExtraction = model.invoke(
            f"{prompt}\n\n=== 待抽取的 PD-ECR 原文 ===\n{content}"
        )

        metadata = PdecrMetadata(**result.metadata.model_dump())
        modules = PdecrModules(
            **{name: getattr(result, name) for name in PdecrModules.model_fields}
        )

        source = SourceInfo(
            source_file=parsed.source_file,
            file_type=parsed.file_type,
            parser=parsed.parser,
            raw_markdown_path=parsed.raw_markdown_path,
            raw_json_path=parsed.raw_json_path,
            checksum=parsed.checksum,
        )

        return PdecrCase(
            case_id=metadata.dc_no or (parsed.source_file or "unknown"),
            source=source,
            metadata=metadata,
            modules=modules,
            quality_control=QualityControl(
                extraction_status="partial",
                confidence=0.7,
                needs_human_review=True,
            ),
        )


def get_extractor() -> Any:
    """按环境返回可用抽取器：有 LLM 用 LLM，否则规则抽取。"""
    if llm_available():
        return LlmExtractor()
    return RuleBasedExtractor()
