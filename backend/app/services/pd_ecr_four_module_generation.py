from __future__ import annotations

from typing import Any

from app.services.pd_ecr_retrieval import retrieve_similar_cases

FOUR_GENERATED_MODULE_IDS = [
    "impact-analysis",
    "validation-plan",
    "implementation-plan",
]

IMPLEMENTATION_CHECKLIST_TEMPLATE: list[tuple[str, str]] = [
    ("Development", "Documents release (drawing, offer drawing, BOM, Spec., ...)"),
    ("Development", "Change BOMs & Drawings & Documents in POE system"),
    ("Development", "Inform documents update (check work-on can met requirements)"),
    ("Development", "Update Offer drawing, TCD, D-FMEA"),
    ("Development", "Norm, WB, HF..."),
    ("Development", "MoC, IMDS"),
    ("Manufacturing", "Related (Production/Testing) equipment be ready on site"),
    ("Manufacturing", "Related (Production/Testing) program be ready"),
    ("Manufacturing", "Related (Production/Testing) tooling / cutting / fixture etc. be ready"),
    ("Manufacturing", "Old tooling / cutting / fixture disposal"),
    ("Manufacturing", "Old materials disposal"),
    ("Manufacturing", "Planner update the planning sheet"),
    ("Manufacturing", "Update FMEA"),
    ("Manufacturing", "Update CP/FC (Control Plan/Flow Chart)"),
    ("Manufacturing", "Update WI/PDS (Include attachments.)"),
    ("Manufacturing", "First batch Mark, Special Mark (Inside Package)"),
    ("Manufacturing", "First batch Mark, Special Mark (Outside Package)"),
    ("Manufacturing", "Training"),
    ("COS", "Confirm the storage of old parts and coordinate the introduction date for new parts"),
    ("COS", "Confirm the delivery date of old parts and first delivery of new parts (FG)"),
    ("COS", "Check sample orders which affected: material order of CKD"),
    ("COS", "Confirm production scheduling according to the alignment, any changes share the information"),
    ("COS", "Confirm the old stock / do prioritize delivery and inventory handling"),
    ("COS", "Inform the first delivery to PMO"),
    ("Purchasing", "Check sample orders which affected: material order of purchasing parts"),
    ("Purchasing", "Inform internal related departments (COS, MFE, MOEx) with following requirements"),
    ("Purchasing", "Update incoming inspection plan"),
    ("Quality", "Update testing program on testing equipment"),
    ("Quality", "Update inspection plan for CKD parts"),
    ("CPjM", "Distribute the Offer drawing, TCD to customer"),
    ("LOP", "Check 10 digit material order"),
    ("PMO", "Check sample orders which affected: Customer order"),
    ("PMO", "Inform Customer the first delivery information"),
    ("Others", ""),
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_cases(similar_cases: list[Any]) -> list[str]:
    values: list[str] = []
    for case in similar_cases:
        case_id = _case_value(case, "case_id")
        if case_id and case_id not in values:
            values.append(case_id)
    return values


def _source_files(similar_cases: list[Any]) -> list[str]:
    values: list[str] = []
    for case in similar_cases:
        files = _case_value(case, "source_files")
        if isinstance(files, list):
            candidates = files
        else:
            candidates = [_case_value(case, "source_file")]
        for file_name in candidates:
            text = _text(file_name)
            if text and text not in values:
                values.append(text)
    return values


def _case_value(case: Any, key: str) -> Any:
    if isinstance(case, dict):
        return case.get(key)
    return getattr(case, key, None)


def _similar_case_payload(case: Any) -> dict[str, Any]:
    if hasattr(case, "model_dump"):
        return case.model_dump(mode="json")
    return dict(case)


def _legacy_input(change_description: dict[str, Any], top_k: int) -> dict[str, Any]:
    summary = _text(change_description.get("changeSummary"))
    title = _text(change_description.get("title"))
    reason = _text(change_description.get("reason")) or summary or title
    description = summary or reason or title
    source = _text(change_description.get("source"))
    part_no = _text(change_description.get("partNumber"))
    product_no = _text(change_description.get("product"))
    customer = _text(change_description.get("customer"))
    remarks = "\n".join(
        item
        for item in [
            f"Source: {source}" if source else "",
            f"Department: {_text(change_description.get('department'))}",
            f"Not change: {_text(change_description.get('notChange'))}",
            "Affected departments: "
            + ", ".join(change_description.get("departments") or []),
        ]
        if item
    )

    return {
        "dc_no": title or "PD-ECR-change-description",
        "date": _text(change_description.get("date")),
        "customer_project": customer,
        "product_no": product_no,
        "part_no": part_no,
        "component_no": part_no,
        "initiator": _text(change_description.get("initiator")) or source,
        "change_source": source,
        "reason": reason,
        "change_reason": reason,
        "change_description": description,
        "change_proposal": description,
        "remarks": remarks,
        "top_k": top_k,
    }


def _impact_module(
    change_description: dict[str, Any],
    source_cases: list[str],
    source_files: list[str],
) -> dict[str, Any]:
    affected_departments = change_description.get("departments") or []
    reason = _text(change_description.get("reason"))
    summary = _text(change_description.get("changeSummary"))
    evidence_note = _evidence_note(source_cases, source_files)

    impact_labels = [
        "Function & Performance will be influenced?",
        "Interface and Appearance will be influenced?",
        "Reliability and robustness will be influenced?",
        "Other components will be influenced?",
        "Manufactory / assembly / testing will be influenced?",
        "Influence on supplier part?",
        "Influence on System / HW / SW / Calibration / Mechanical?",
        "Influence on cost?",
    ]
    impacts = []
    for index, label in enumerate(impact_labels):
        likely_yes = index in {0, 2, 4} or (
            index == 3 and bool(affected_departments)
        )
        impacts.append(
            {
                "no": not likely_yes,
                "yes": likely_yes,
                "confirmedBy": "",
                "confirmedAt": "",
                "desc": _impact_desc(label, summary, reason, evidence_note)
                if likely_yes
                else "",
            }
        )

    doc_labels = [
        "Interface FMEA relevant / IFMEA",
        "Product FMEA relevant / DFMEA",
        "Special Characteristics relevant / PSC",
        "IMDS relevant",
        "Offer drawing relevant",
        "TCD relevant",
        "Norm, WB, HF... relevant",
        "WI check",
    ]
    documents = [
        {
            "no": index not in {0, 1, 4, 5, 7},
            "yes": index in {0, 1, 4, 5, 7},
            "respPerson": "",
            "dueDate": "",
        }
        for index, _ in enumerate(doc_labels)
    ]

    data = {
        "impacts": impacts,
        "documents": documents,
        "mixedDeliveries": "YES",
        "mixedDeliveryRemark": "Review historical cases and confirm mixing rule with Quality/Logistics.",
        "firstDeliveryAnswer": "Keep same delivery control unless customer or quality requires special marking.",
        "stockDeliveryRows": [
            {
                "label": "Raw materials",
                "zh": "原材料",
                "options": ["Not affect", "Use in other products", "Scrap", "Rework", "Use up"],
                "checked": ["Not affect"],
                "remark": "",
            },
            {
                "label": "Parts/Subassemble",
                "zh": "零件/分总成",
                "options": ["Not affect", "Use in other products", "Scrap", "Rework", "Use up"],
                "checked": ["Not affect"],
                "remark": "",
            },
            {
                "label": "Finished goods(inhouse)",
                "zh": "厂内成品",
                "options": ["Not affect", "Scrap", "Rework", "Use up"],
                "checked": ["Not affect"],
                "remark": "",
            },
            {
                "label": "Finished goods(RDCK外库)",
                "zh": "RDCK外库成品",
                "options": ["Not affect", "Scrap", "Rework", "Use up"],
                "checked": ["Not affect"],
                "remark": "",
            },
            {
                "label": "Finished goods(customer)",
                "zh": "客户处成品",
                "options": ["Not affect", "Recall", "Rework"],
                "checked": ["Not affect"],
                "remark": "",
            },
        ],
        "costNote": "Cost impact needs Purchasing/Controlling confirmation.",
    }
    return _module(
        "impact-analysis",
        "影响分析",
        "Impact analysis generated from Change Description and historical cases.",
        data,
        source_cases,
        source_files,
    )


def _impact_desc(label: str, summary: str, reason: str, evidence_note: str) -> str:
    base = summary or reason or "Change Description input"
    return f"Check {label} for {base}. {evidence_note}"


def _validation_module(
    source_cases: list[str],
    source_files: list[str],
) -> dict[str, Any]:
    checked = {
        "Try run",
        "Capability Studies CMK",
        "BOM check",
        "Test report",
    }
    rows = [
        {
            "id": f"ai-{label.lower().replace(' ', '-')}",
            "label": label,
            "checked": label in checked,
            "criteria": "Confirm acceptance criteria from historical similar PD-ECR cases.",
            "finishDate": "",
            "respPerson": "",
            "comments": _evidence_note(source_cases, source_files)
            if label in checked
            else "",
        }
        for label in [
            "Try run",
            "Capability Studies CMK",
            "Capability Studies MSA",
            "MAE release",
            "Cleanness test",
            "QZ test",
            "200h PDL",
            "BOM check",
            "Test report",
            "PAV release",
            "Other",
        ]
    ]
    return _module(
        "validation-plan",
        "QAC & Validation Results",
        "QAC and validation results generated from similar historical cases.",
        {"rows": rows},
        source_cases,
        source_files,
    )


def _implementation_module(
    change_description: dict[str, Any],
    source_cases: list[str],
    source_files: list[str],
) -> dict[str, Any]:
    checklist = [
        {
            "id": f"ai-import-{index + 1:02d}",
            "department": department,
            "yn": _implementation_yn(change_description, department, description),
            "description": description,
            "responsible": "",
            "dueDate": "",
            "result": "",
            "resultNote": "",
        }
        for index, (department, description) in enumerate(IMPLEMENTATION_CHECKLIST_TEMPLATE)
    ]

    data = {
        "developmentConfirmation": _evidence_note(source_cases, source_files),
        "implementationDate": "",
        "checklistRows": checklist,
    }
    return _module(
        "implementation-plan",
        "实施与验证结果",
        "Implementation and validation results checklist generated from historical patterns.",
        data,
        source_cases,
        source_files,
    )


def _implementation_yn(
    change_description: dict[str, Any],
    department: str,
    description: str,
) -> str:
    if department == "Others" and not description:
        return ""

    selected_departments = {
        _text(value).lower()
        for value in change_description.get("departments") or []
        if _text(value)
    }
    aliases = {
        "development": {"development", "dev", "eng", "engineering", "研发"},
        "manufacturing": {"manufacturing", "mfe", "moex", "production", "manufacture", "生产", "制造"},
        "quality": {"quality", "qac", "qa", "qc", "质量"},
        "purchasing": {"purchasing", "purchase", "supplier", "采购"},
        "cos": {"cos", "logistics", "supply chain", "物流"},
        "cpjm": {"cpjm", "project", "customer project"},
        "lop": {"lop"},
        "pmo": {"pmo", "customer order"},
    }
    department_key = department.lower()
    if selected_departments:
        if department_key in selected_departments:
            return "Y"
        if aliases.get(department_key, set()) & selected_departments:
            return "Y"
        return "N"

    query_text = " ".join(
        _text(change_description.get(key))
        for key in ["changeSummary", "reason", "source", "notChange", "title"]
    ).lower()
    department_keywords = {
        "development": ["drawing", "document", "bom", "spec", "tcd", "d-fmea", "moc", "imds", "design"],
        "manufacturing": ["production", "testing", "tooling", "fixture", "process", "assembly", "material", "training", "fmea", "wi", "pds"],
        "cos": ["stock", "delivery", "ckd", "fg", "schedule", "inventory"],
        "purchasing": ["supplier", "purchasing", "purchase", "incoming"],
        "quality": ["quality", "inspection", "validation", "qac", "test"],
        "cpjm": ["customer", "offer drawing", "tcd"],
        "lop": ["material order", "10 digit"],
        "pmo": ["customer order", "delivery"],
    }
    if any(keyword in query_text for keyword in department_keywords.get(department_key, [])):
        return "Y"
    return "N"


def _evidence_note(source_cases: list[str], source_files: list[str]) -> str:
    if source_cases or source_files:
        refs = ", ".join(source_cases or source_files)
        return f"Grounded by similar historical case(s): {refs}."
    return "No close historical case found; please confirm manually."


def _module(
    module_id: str,
    title: str,
    summary: str,
    data: dict[str, Any],
    source_cases: list[str],
    source_files: list[str],
) -> dict[str, Any]:
    warnings = [] if source_cases or source_files else ["No historical evidence was available."]
    return {
        "id": module_id,
        "title": title,
        "summary": summary,
        "data": data,
        "source_cases": source_cases,
        "source_files": source_files,
        "needs_human_input": not (source_cases or source_files),
        "warnings": warnings,
    }


def generate_modules_from_change_description(
    change_description: dict[str, Any],
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    input_data = _legacy_input(change_description, top_k)
    _, similar_cases = retrieve_similar_cases(input_data, top_k=top_k)
    similar_payloads = [_similar_case_payload(case) for case in similar_cases]
    source_cases = _source_cases(similar_cases)
    source_files = _source_files(similar_cases)

    return {
        "input_snapshot": input_data,
        "similar_cases": similar_payloads,
        "generated_module_ids": FOUR_GENERATED_MODULE_IDS,
        "modules": [
            _impact_module(change_description, source_cases, source_files),
            _validation_module(source_cases, source_files),
            _implementation_module(change_description, source_cases, source_files),
        ],
    }
