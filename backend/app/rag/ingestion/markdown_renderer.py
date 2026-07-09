"""Markdown 渲染：标准 PdecrCase -> 固定结构 Markdown。

Markdown 只由 PdecrCase JSON 生成，绝不直接使用 raw markdown，
以保证知识库里人读的 md 与主数据一致、结构可预测。
"""

from __future__ import annotations

from app.rag.schemas.pdecr_case_schema import PdecrCase


def _module(value: str | None) -> str:
    return (
        value.strip() if value and value.strip() else "_（未抽取到 / Not extracted）_"
    )


def _list(values: list[str]) -> str:
    return "、".join(values) if values else "_（空）_"


def _change_title(case: PdecrCase) -> str:
    """标题用变更方案首句 / 变更原因兜底。"""
    for candidate in (case.modules.change_proposal, case.modules.change_reason):
        if candidate and candidate.strip():
            first_line = candidate.strip().splitlines()[0]
            return first_line[:80]
    return ""


def render_markdown(case: PdecrCase) -> str:
    md = case.metadata
    lines: list[str] = []

    lines.append(f"# {case.case_id} {_change_title(case)}".rstrip())
    lines.append("")

    # 1. Basic Information
    lines.append("## 1. Basic Information")
    lines.append("")
    lines.append(f"- DC No: {md.dc_no or '_（空）_'}")
    lines.append(f"- Date: {md.date or '_（空）_'}")
    lines.append(f"- MCR No: {md.mcr_no or '_（空）_'}")
    lines.append(f"- Customer Project: {_list(md.customer_project)}")
    lines.append(f"- Affected Product No: {_list(md.affected_product_no)}")
    lines.append(f"- Component No: {_list(md.component_no)}")
    lines.append(f"- Initiator: {md.initiator or '_（空）_'}")
    lines.append(f"- Department: {md.department or '_（空）_'}")
    lines.append(f"- Product Family: {md.product_family or '_（空）_'}")
    lines.append(f"- Change Type: {md.change_type or '_（空）_'}")
    lines.append("")

    # 2-8 业务模块
    section_map = [
        ("2. Change Reason", case.modules.change_reason),
        ("3. Current Design", case.modules.current_design),
        ("4. Change Proposal", case.modules.change_proposal),
        ("5. Impact Analysis", case.modules.impact_analysis),
        ("6. Validation Plan", case.modules.validation_plan),
        ("7. Implementation Plan", case.modules.implementation_plan),
        ("8. Risk Analysis", case.modules.risk_analysis),
    ]
    for title, content in section_map:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(_module(content))
        lines.append("")

    # 影响部门（若有）附在影响分析之后不重复；这里放进对应模块正文即可，
    # 结构化的部门清单单独以列表呈现在 Impact Analysis 之下：
    if case.impact_departments:
        lines.append("### Impacted Departments")
        lines.append("")
        for dep in case.impact_departments:
            flag = {True: "受影响", False: "不受影响", None: "未知"}[dep.is_impacted]
            lines.append(
                f"- {dep.department or '?'} [{flag}]: "
                f"{dep.impact_content or ''} "
                f"(负责人: {dep.responsible_person or '-'})"
            )
        lines.append("")

    # 9. Tasks
    lines.append("## 9. Tasks")
    lines.append("")
    if case.tasks:
        lines.append("| Task | Owner | Department | Plan | Result | Status |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for t in case.tasks:
            lines.append(
                f"| {t.task_name or ''} | {t.owner or ''} | {t.department or ''} "
                f"| {(t.plan or '').replace(chr(10), ' ')} "
                f"| {(t.result or '').replace(chr(10), ' ')} | {t.status or ''} |"
            )
    else:
        lines.append(_module(None))
    lines.append("")

    # 10. Approval Summary
    lines.append("## 10. Approval Summary")
    lines.append("")
    lines.append(_module(case.modules.approval_summary))
    lines.append("")

    # 11. Attachments
    lines.append("## 11. Attachments")
    lines.append("")
    if case.attachments:
        for a in case.attachments:
            lines.append(
                f"- {a.file_name or '?'} ({a.file_type or '-'}) "
                f"→ {a.related_module or '-'}  {a.path or ''}".rstrip()
            )
    else:
        lines.append(_module(None))
    lines.append("")

    # 12. Extraction Quality
    qc = case.quality_control
    lines.append("## 12. Extraction Quality")
    lines.append("")
    lines.append(f"- Extraction Status: {qc.extraction_status}")
    lines.append(
        f"- Confidence: {qc.confidence if qc.confidence is not None else '_（空）_'}"
    )
    lines.append(f"- Needs Human Review: {qc.needs_human_review}")
    lines.append(f"- Missing Fields: {_list(qc.missing_fields)}")
    if qc.errors:
        lines.append(f"- Errors: {'; '.join(qc.errors)}")
    if case.modules.remarks:
        lines.append("")
        lines.append("### Remarks")
        lines.append("")
        lines.append(case.modules.remarks.strip())
    lines.append("")

    return "\n".join(lines)
