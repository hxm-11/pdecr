"""归一化：把抽取出的 PdecrCase 规整成干净、可入库的标准形态。

职责：
  - 字段名归一（dc_no / PD-ECR No / PDECR No -> dc_no，由抽取器负责别名，
    这里做值层面的清洗）。
  - customer_project / affected_product_no / component_no 统一为 list[str]。
  - 日期统一为 YYYY-MM-DD。
  - 空值统一：标量空 -> None，列表空 -> []。
  - 生成稳定 case_id：优先 dc_no，否则用 source_file 的 hash。
  - 调 validate_case 体检，写入 quality_control。
"""

from __future__ import annotations

import hashlib
import re

from app.rag.schemas.pdecr_case_schema import (
    MODULE_NAMES,
    PdecrCase,
    validate_case,
)

_DATE_PATTERNS = [
    re.compile(r"(\d{4})[\-/年.](\d{1,2})[\-/月.](\d{1,2})"),
    re.compile(r"(\d{4})(\d{2})(\d{2})"),  # 20260422
]

# 常见多值分隔符
_SPLIT_RE = re.compile(r"[;,；，\n]| and | & ")


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if m:
            y, mo, d = m.groups()
            try:
                return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            except ValueError:
                return None
    return None


def to_str_list(value) -> list[str]:
    """把标量 / 字符串 / 列表统一成去重后的 list[str]（保序）。"""
    if value is None:
        return []
    items: list[str] = []
    if isinstance(value, list):
        raw = value
    else:
        raw = _SPLIT_RE.split(str(value))
    seen: set[str] = set()
    for item in raw:
        s = str(item).strip().strip("'\"")
        if s and s.lower() not in {"n/a", "na", "-", "none", "null"} and s not in seen:
            seen.add(s)
            items.append(s)
    return items


def _clean_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"n/a", "na", "-", "none", "null"}:
        return None
    return s


def _stable_case_id(case: PdecrCase) -> str:
    dc_no = _clean_scalar(case.metadata.dc_no)
    if dc_no:
        # 统一成 PDECR<dcno> 形式，去掉非字母数字下划线
        norm = re.sub(r"[^0-9A-Za-z_]", "_", dc_no)
        return f"PDECR_{norm}" if not norm.upper().startswith("PDECR") else norm
    basis = case.source.source_file or case.source.checksum or "unknown"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"CASE_{digest}"


def normalize_case(case: PdecrCase) -> PdecrCase:
    """就地清洗并返回同一个 case（也返回，方便链式）。"""
    md = case.metadata

    # 标量清洗
    md.dc_no = _clean_scalar(md.dc_no)
    md.mcr_no = _clean_scalar(md.mcr_no)
    md.initiator = _clean_scalar(md.initiator)
    md.department = _clean_scalar(md.department)
    md.product_family = _clean_scalar(md.product_family)
    md.change_type = _clean_scalar(md.change_type)
    md.date = normalize_date(md.date)

    # 多值统一为 list[str]
    md.customer_project = to_str_list(md.customer_project)
    md.affected_product_no = to_str_list(md.affected_product_no)
    md.component_no = to_str_list(md.component_no)

    # 模块空串 -> None
    for name in MODULE_NAMES:
        val = getattr(case.modules, name)
        setattr(case.modules, name, _clean_scalar(val))

    # 稳定 case_id
    case.case_id = _stable_case_id(case)

    # 体检 -> quality_control
    report = validate_case(case)
    qc = case.quality_control
    qc.missing_fields = report["missing_fields"]
    filled = report["filled_modules"]
    key_meta_missing = any(f.startswith("metadata.") for f in report["missing_fields"])
    if not filled and not any([md.dc_no, md.customer_project, md.affected_product_no]):
        qc.extraction_status = "failed"
    elif filled and not key_meta_missing:
        qc.extraction_status = "complete"
    else:
        qc.extraction_status = "partial"
    # 只要还有关键缺失或状态非 complete，就建议人工复核
    qc.needs_human_review = qc.extraction_status != "complete"

    return case
