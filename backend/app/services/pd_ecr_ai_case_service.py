from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
from jinja2 import BaseLoader, Environment
from sqlmodel import Session

from app.models import PdEcrCaseCreate, PdEcrModuleUpdate, User
from app.services.pd_ecr_case_service import (
    create_case,
    ensure_module_edit_access,
    get_case_or_404,
    list_modules,
    serialize_case,
    serialize_module,
    update_module,
)
from app.services.pd_ecr_generation import generate_grounded_draft


V1_TO_EDITABLE_MODULE_IDS = {
    "basic_information": "change-description",
    "change_description": "impact-analysis",
    "reason_for_change": "validation-plan",
    "impact_analysis": "validation-result",
    "implementation_plan": "implementation-plan",
    "approval_signoff_information": "implementation-result",
}

TEMPLATES_PRE_DIR = Path(__file__).resolve().parents[1] / "templates_pre"

EDITABLE_TEMPLATE_FILES = {
    "impact-analysis": "2impact.md",
    "validation-plan": "3validation_plan.md",
    "validation-result": "4Valiation_result.md",
    "implementation-plan": "5implementation_plan.md",
    "implementation-result": "6Implementation_result.md",
}


def _case_no_from_input(input_data: dict[str, Any], draft_id: str) -> str:
    return str(
        input_data.get("dc_no")
        or input_data.get("case_no")
        or input_data.get("mcr_no")
        or draft_id
    )


def _editable_module_id(module_id: Any) -> str:
    value = str(module_id or "").strip()
    return V1_TO_EDITABLE_MODULE_IDS.get(value, value.replace("_", "-"))


def _template_context(input_snapshot: dict[str, Any], content: str) -> dict[str, Any]:
    component_no = input_snapshot.get("component_no") or input_snapshot.get("part_no") or ""
    basic_info = {
        "dc_no": input_snapshot.get("dc_no") or "",
        "date": input_snapshot.get("date") or "",
        "customer_project": input_snapshot.get("customer_project") or "",
        "mcr_no": input_snapshot.get("mcr_no") or "",
        "product_no": input_snapshot.get("product_no") or "",
        "component_no": component_no,
        "initiator": input_snapshot.get("initiator") or input_snapshot.get("change_source") or "",
    }
    return {
        **input_snapshot,
        "basic_info": basic_info,
        "change_request": {
            "reason": input_snapshot.get("change_reason") or "",
            "current_design": input_snapshot.get("current_design") or "",
            "change_proposal": input_snapshot.get("change_proposal")
            or input_snapshot.get("change_description")
            or "",
            "remarks": input_snapshot.get("remarks") or "",
        },
        "change_reason": input_snapshot.get("change_reason") or "",
        "reason": input_snapshot.get("change_reason") or "",
        "current_design": input_snapshot.get("current_design") or "",
        "change_proposal": input_snapshot.get("change_proposal")
        or input_snapshot.get("change_description")
        or "",
        "remarks": input_snapshot.get("remarks") or "",
        "now": input_snapshot.get("current_design") or "",
        "after": input_snapshot.get("change_description") or content,
        "implementation_plan": content,
        "revision_description": content,
    }


def _render_templates_pre(template_file: str, context: dict[str, Any]) -> str:
    template_path = TEMPLATES_PRE_DIR / template_file
    if not template_path.exists():
        return ""

    template_text = template_path.read_text(encoding="utf-8", errors="ignore")
    env = Environment(loader=BaseLoader(), autoescape=False)
    return env.from_string(template_text).render(**context)


def _rag_results_from_draft(draft: Any) -> list[dict[str, Any]]:
    return [
        {
            "case_id": item.case_id,
            "source_file": item.source_file,
            "matched_fields": item.matched_fields,
            "similarity_score": item.similarity_score,
            "module_summary": item.module_summary,
        }
        for item in draft.similar_cases
    ]


def _module_prompt(editable_id: str, template_file: str | None) -> str:
    template_note = (
        f"templates_pre/{template_file}"
        if template_file
        else "the editable Change Request description form"
    )
    return (
        "AI prompt: use the submitted change source, change reason, change "
        f"description, and retrieved similar cases to complete {template_note}. "
        "Cite retrieved cases and mark unsupported fields for human input."
    )


def _module_payloads_from_draft(draft: Any) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    input_snapshot = draft.input_snapshot.model_dump(mode="json")
    rag_results = _rag_results_from_draft(draft)
    for module in draft.modules:
        module_data = module.model_dump(mode="json")
        editable_id = _editable_module_id(module_data["module_id"])
        generated_content = str(module_data.get("content") or "")
        template_file = EDITABLE_TEMPLATE_FILES.get(editable_id)
        rendered_content = (
            _render_templates_pre(
                template_file,
                _template_context(input_snapshot, generated_content),
            )
            if template_file
            else generated_content
        )
        modules.append(
            {
                "module_id": editable_id,
                "title": module_data["title"],
                "content_md": rendered_content,
                "content_json": {
                    "summary": module_data.get("summary") or "",
                    "warnings": module_data.get("warnings") or [],
                    "generated_from": "ai",
                    "draft_id": draft.draft_id,
                    "v1_module_id": module_data["module_id"],
                    "content": rendered_content,
                    "template_file": template_file,
                    "rag_retrieval_results": rag_results,
                    "ai_prompt": _module_prompt(editable_id, template_file),
                },
                "source_cases": module_data.get("source_cases") or [],
                "source_files": module_data.get("source_files") or [],
                "needs_human_input": bool(module_data.get("needs_human_input")),
            }
        )
    return modules


def _module_by_id(*, session: Session, case_id: Any, module_id: str):
    for module in list_modules(session=session, case_id=case_id):
        if module.module_id == module_id:
            return module
    raise HTTPException(status_code=404, detail="PD-ECR module not found")


def _generated_module_by_editable_id(draft: Any, module_id: str):
    for module in draft.modules:
        module_data = module.model_dump(mode="json")
        if _editable_module_id(module_data["module_id"]) == module_id:
            return module_data
    raise HTTPException(
        status_code=404,
        detail=f"Generated module not found: {module_id}",
    )


def create_case_from_ai(
    *,
    session: Session,
    input_data: dict[str, Any],
    current_user: User,
    similar_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    draft = generate_grounded_draft(input_data, similar_cases=similar_cases)
    case_in = PdEcrCaseCreate(
        case_no=_case_no_from_input(input_data, draft.draft_id),
        title=str(
            input_data.get("change_description")
            or input_data.get("title")
            or "AI generated PD-ECR draft"
        )[:500],
        status="draft",
        source_type="ai_generated",
        is_historical=False,
        dc_no=input_data.get("dc_no"),
        mcr_no=input_data.get("mcr_no"),
        customer_project=input_data.get("customer_project"),
        product_no=input_data.get("product_no"),
        part_no=input_data.get("part_no") or input_data.get("component_no"),
        change_type=input_data.get("change_type"),
        initiator=input_data.get("initiator"),
        modules=_module_payloads_from_draft(draft),
    )
    case = create_case(session=session, case_in=case_in, current_user=current_user)
    modules = list_modules(session=session, case_id=case.id)
    return {
        "case": serialize_case(case),
        "modules": [serialize_module(module) for module in modules],
        "draft_id": draft.draft_id,
        "draft_status": draft.draft_status.value,
        "warnings": [
            warning for module in draft.modules for warning in module.warnings
        ],
        "redirect_to": f"/pd-ecr/cases/{case.id}",
    }


def regenerate_module_preview(
    *,
    session: Session,
    case_id: str,
    module_id: str,
    current_user: User,
    instruction: str | None = None,
) -> dict[str, Any]:
    case = get_case_or_404(session=session, case_id=case_id)
    module = _module_by_id(session=session, case_id=case.id, module_id=module_id)
    ensure_module_edit_access(case, module, current_user)
    input_data = {
        "dc_no": case.dc_no or case.case_no,
        "mcr_no": case.mcr_no or "",
        "customer_project": case.customer_project or "",
        "product_no": case.product_no or "",
        "part_no": case.part_no or "",
        "change_type": case.change_type or "",
        "change_description": case.title or module.content_md or "",
        "change_reason": instruction or (module.content_json or {}).get("summary") or "",
    }
    draft = generate_grounded_draft(input_data, similar_cases=[])
    generated_module = _generated_module_by_editable_id(draft, module_id)
    return {
        "case_id": str(case.id),
        "module_id": module_id,
        "title": generated_module["title"],
        "content_md": generated_module.get("content") or "",
        "content_json": {
            "summary": generated_module.get("summary") or "",
            "warnings": generated_module.get("warnings") or [],
            "generated_from": "module_regenerate",
            "draft_id": draft.draft_id,
            "v1_module_id": generated_module["module_id"],
            "instruction": instruction or "",
        },
        "source_cases": generated_module.get("source_cases") or [],
        "source_files": generated_module.get("source_files") or [],
        "needs_human_input": bool(generated_module.get("needs_human_input")),
    }


def apply_generated_module(
    *,
    session: Session,
    case_id: str,
    module_id: str,
    generated: dict[str, Any],
    expected_version: int,
    current_user: User,
) -> dict[str, Any]:
    case = get_case_or_404(session=session, case_id=case_id)
    updated = update_module(
        session=session,
        case=case,
        module_id=module_id,
        module_in=PdEcrModuleUpdate(
            title=generated.get("title"),
            content_md=generated.get("content_md") or "",
            content_json=generated.get("content_json") or {},
            source_cases=generated.get("source_cases") or [],
            source_files=generated.get("source_files") or [],
            needs_human_input=bool(generated.get("needs_human_input")),
            expected_version=expected_version,
        ),
        current_user=current_user,
    )
    return {"module": serialize_module(updated)}
