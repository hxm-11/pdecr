"""基于正则 + 关键词的初步抽取器（无需 LLM）。

作为 LLM 抽取器不可用时的回退，也可用于离线冒烟测试。
原则：抽不到就留空（None / []），绝不编造；抽到的重要字段附 evidence。

它复用 app/rag/pdecr_schema.py 里的字段别名，尽量与既有模板对齐。
"""

from __future__ import annotations

import re
from typing import Any

from app.rag.pdecr_schema import IDENTIFICATION_FIELDS
from app.rag.schemas.pdecr_case_schema import (
    PdecrCase,
    PdecrMetadata,
    PdecrModules,
    QualityControl,
    SourceInfo,
)

from ..loaders import ParsedDocument

# 模块 -> 触发关键词（中英）。用于把正文粗切成业务模块段落。
_MODULE_KEYWORDS: dict[str, list[str]] = {
    "change_reason": [
        "变更原因",
        "更改原因",
        "更改理由",
        "变更理由",
        "reason of change",
        "reason for change",
    ],
    "current_design": [
        "当前设计",
        "现设计",
        "原设计",
        "current design",
        "current status",
    ],
    "change_proposal": [
        "变更方案",
        "变更描述",
        "更改建议",
        "更改方案",
        "change proposal",
        "change description",
        "proposed change",
    ],
    "impact_analysis": ["影响分析", "影响评估", "impact analysis", "impact assessment"],
    "validation_plan": [
        "验证计划",
        "验证方案",
        "验证项",
        "validation plan",
        "validation",
    ],
    "implementation_plan": [
        "实施计划",
        "执行计划",
        "implementation plan",
        "implementation",
    ],
    "risk_analysis": ["风险分析", "风险评估", "risk analysis", "risk assessment"],
    "approval_summary": [
        "审批",
        "批准",
        "签字",
        "会签",
        "approval",
        "sign off",
        "sign-off",
    ],
    "remarks": ["备注", "其他说明", "remarks", "notes"],
}

# 元数据 label -> 归一化 key（补充 pdecr_schema 未覆盖的）
# rule-based 单值最大长度（超过多半是把整张表/HTML 抓进来了）
_MAX_VALUE_LEN = 120

_DATE_RE = re.compile(r"(\d{4})[\-/年.](\d{1,2})[\-/月.](\d{1,2})")
_DC_NO_RE = re.compile(
    r"(PD[\-_ ]?ECR)[\s_]*(?:No\.?[:：]?)?\s*[_#]?\s*(\d{2}[_\-]?\d{2,3})",
    re.IGNORECASE,
)


def _clean_value(raw: str) -> str:
    """规则抽取的单值清洗：遇到 HTML 标签/表格切断，去多余空白并截断。

    MinerU 的 markdown 常把整张表压到一行，若不切断，label 后会把整段表格
    误当成字段值。这里在第一个 HTML 标签处截断，只保留紧跟 label 的短值。
    """
    value = raw.strip()
    # 在第一个 HTML 标签处截断（<td> / </tr> / <table> 等）
    tag_idx = value.find("<")
    if tag_idx != -1:
        value = value[:tag_idx]
    # 只取到下一个明显的字段标签前（连续多个空格通常是下一个单元格）
    value = re.split(r"\s{3,}", value)[0]
    value = value.strip(" :：=\t|")
    if len(value) > _MAX_VALUE_LEN:
        value = value[:_MAX_VALUE_LEN].rstrip()
    return value


class RuleBasedExtractor:
    extractor_name = "rule_based"

    def extract(self, parsed: ParsedDocument) -> PdecrCase:
        text = parsed.full_text()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        metadata = self._extract_metadata(text, lines, parsed.source_file)
        modules = self._extract_modules(lines)

        source = SourceInfo(
            source_file=parsed.source_file,
            file_type=parsed.file_type,
            parser=parsed.parser,
            raw_markdown_path=parsed.raw_markdown_path,
            raw_json_path=parsed.raw_json_path,
            checksum=parsed.checksum,
        )

        # case_id 先用 dc_no / 文件名兜底，正式稳定 id 由 normalizer 生成
        provisional_id = metadata.dc_no or (parsed.source_file or "unknown")

        return PdecrCase(
            case_id=provisional_id,
            source=source,
            metadata=metadata,
            modules=modules,
            quality_control=QualityControl(
                extraction_status="partial",
                confidence=0.3,  # rule-based 置信度低，默认需人工复核
                needs_human_review=True,
            ),
        )

    # ── 元数据 ────────────────────────────────────────────
    def _extract_metadata(
        self, text: str, lines: list[str], source_file: str | None
    ) -> PdecrMetadata:
        md = PdecrMetadata()

        # dc_no：先从正文找 PD-ECR No，再从文件名兜底（PDECR24_093 → 24_093）
        m = _DC_NO_RE.search(text)
        if m:
            md.dc_no = m.group(2).replace("-", "_")
        elif source_file:
            fm = re.search(
                r"PDECR[\s_]?(\d{2})[_\-](\d{2,3})", source_file, re.IGNORECASE
            )
            if fm:
                md.dc_no = f"{fm.group(1)}_{fm.group(2)}"

        # date → YYYY-MM-DD
        dm = _DATE_RE.search(text)
        if dm:
            y, mo, d = dm.groups()
            md.date = f"{y}-{int(mo):02d}-{int(d):02d}"

        md.mcr_no = self._find_label_value(lines, IDENTIFICATION_FIELDS["mcr_no"])
        md.change_type = self._find_label_value(
            lines, IDENTIFICATION_FIELDS["change_type"]
        )
        md.initiator = self._find_label_value(lines, IDENTIFICATION_FIELDS["initiator"])

        cp = self._find_label_value(lines, IDENTIFICATION_FIELDS["customer_project"])
        if cp:
            md.customer_project = [cp]
        prod = self._find_label_value(lines, IDENTIFICATION_FIELDS["product_no"])
        if prod:
            md.affected_product_no = [prod]
        comp = self._find_label_value(lines, IDENTIFICATION_FIELDS["part_no"])
        if comp:
            md.component_no = [comp]

        return md

    @staticmethod
    def _find_label_value(lines: list[str], field_def: dict[str, Any]) -> str | None:
        """在 "label: value" 或 "label\tvalue" 行里找值。"""
        labels = [field_def["label"], *field_def.get("aliases", [])]
        for line in lines:
            for label in labels:
                # 允许 label 后跟 : ： = \t 空格
                pattern = re.compile(
                    rf"{re.escape(label)}\s*[:：=\t]\s*(.+)", re.IGNORECASE
                )
                m = pattern.search(line)
                if m:
                    value = _clean_value(m.group(1))
                    if value and value.lower() not in {"n/a", "na", "-", "none"}:
                        return value
        return None

    # ── 模块 ──────────────────────────────────────────────
    def _extract_modules(self, lines: list[str]) -> PdecrModules:
        modules = PdecrModules()
        # 为每一行标注它属于哪个模块（命中关键词则切换当前模块）
        current: str | None = None
        buckets: dict[str, list[str]] = {name: [] for name in _MODULE_KEYWORDS}

        for line in lines:
            matched = self._match_module(line)
            if matched:
                current = matched
                # 关键词后面同一行如果还有内容，也收进去
                tail = self._strip_module_label(line, matched)
                if tail:
                    buckets[current].append(tail)
                continue
            if current:
                buckets[current].append(line)

        for name, collected in buckets.items():
            joined = "\n".join(collected).strip()
            if joined:
                setattr(modules, name, joined)
        return modules

    @staticmethod
    def _match_module(line: str) -> str | None:
        low = line.lower()
        for name, keywords in _MODULE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in low:
                    return name
        return None

    @staticmethod
    def _strip_module_label(line: str, module: str) -> str:
        low = line.lower()
        for kw in _MODULE_KEYWORDS[module]:
            idx = low.find(kw.lower())
            if idx != -1:
                tail = line[idx + len(kw) :].lstrip(" :：=\t-")
                return tail.strip()
        return ""
