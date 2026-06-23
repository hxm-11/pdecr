from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.services.pd_ecr_patterns import (
    ChangeTypePattern,
    get_pattern,
    load_pattern_library,
    pattern_to_prompt_context,
)
from app.services.pd_ecr_retrieval import retrieve_similar_cases
from app.services.pd_ecr_schema import (
    ChangeTypeCategory,
    ClassificationResult,
    DraftStatus,
    GeneratedDraft,
    GeneratedModule,
    MODULE_TITLES,
    NewPdEcrRequest,
    PdEcrModuleId,
    SimilarCaseResult,
)

# Feature flag: set PD_ECR_USE_PATTERN_RETRIEVAL=true to enable pattern-based prompts
_USE_PATTERN_RETRIEVAL = os.getenv("PD_ECR_USE_PATTERN_RETRIEVAL", "false").lower() in (
    "true",
    "1",
    "yes",
)


# ---------------------------------------------------------------------------
# Anti-copying rules — embedded in every pattern-migration prompt
# ---------------------------------------------------------------------------
ANTI_COPY_RULES = """## ANTI-COPYING RULES (MANDATORY)

These rules protect data integrity and prevent incorrect identifier leakage:

1. **NEVER copy part numbers** (like F01ZH003G1-00, F01Z5017P5-05, F01Z5018CM-01)
   from historical cases. Use ONLY part numbers from the NEW request's input fields.

2. **NEVER copy project names** (JIM-493, JIE-4JJ, JIM-PT611, JIM-4JJ)
   from historical cases. Use ONLY the project name from the NEW request.

3. **NEVER copy person names** (卢青松, 沈伟博, 杨广拓, 谢支福, 王笛, etc.)
   from historical cases. Use role titles like "Design Engineer" or leave for human input.

4. **NEVER copy dates** from historical cases. Use the current date or leave blank.

5. **NEVER copy complete sentences verbatim** from historical evidence snippets.
   Always rephrase in the context of the new request's product, project, and change scope.

6. **ALWAYS cite** which historical pattern informed each module
   (e.g., "Pattern: first_sample_release from PDECR24_093") rather than
   copying the content directly."""


PATTERN_MIGRATION_SYSTEM_PROMPT = """You are an engineering change management assistant for automotive
aftertreatment systems (Bosch Powerrain Solutions).

Your task is to draft PD-ECR documents by MIGRATING PROCESS PATTERNS —
not copying content — from historical engineering changes to a new
change request context.

## WHAT "PATTERN MIGRATION" MEANS

A "pattern" is the abstract process, checklist, risk assessment framework,
or approval workflow that was followed in a historical case. It is NOT
the specific product/part/person data from that case.

Example:
- Historical case: "PDECR24_093 — Flange shape changed for JIM-493 A-Sample,
  required CFD simulation"
- Pattern extracted: "When a geometric interface changes at A-Sample stage,
  CFD simulation is needed to verify interface compatibility"
- Applied to new case: "Your [component] change at [NEW PROJECT] A-Sample
  may need CFD simulation to verify interface compatibility with [NEW
  BOUNDARY CONDITIONS]"

## HOW TO APPLY THIS

For each module:
1. Identify the applicable pattern(s) from the provided historical evidence
2. Adapt the pattern's structure (checklist items, risk areas, approval
   roles, verification types) to the new request's context
3. Fill in specifics ONLY from the new request's input fields
4. If the pattern doesn't cover something, set needs_human_input=true and
   explain what specific information is missing
5. List which patterns you applied in the applied_patterns field
"""


DRAFT_CACHE: dict[str, GeneratedDraft] = {}


def build_generation_prompt(
    request: NewPdEcrRequest,
    similar_cases: list[SimilarCaseResult],
    *,
    classification: ClassificationResult | None = None,
) -> str:
    """Build the LLM generation prompt — pattern-aware when flag is on.

    When PD_ECR_USE_PATTERN_RETRIEVAL=true, uses pattern-migration framing
    with structured pattern context and anti-copying rules.
    """

    evidence = [
        {
            "case_id": item.case_id,
            "source_file": item.source_file,
            "matched_fields": item.matched_fields,
            "module_summary": item.module_summary,
            "pattern_category": item.pattern_category,
            "snippets": [
                snippet.model_dump(mode="json")
                for snippet in item.retrieval_context.evidence_snippets
            ],
        }
        for item in similar_cases
    ]

    if _USE_PATTERN_RETRIEVAL and classification is not None:
        # --- Pattern-migration prompt ---
        pattern_context = ""
        if classification.category != ChangeTypeCategory.UNKNOWN:
            pattern = get_pattern(classification.category)
            if pattern:
                pattern_context = f"""
## APPLICABLE CHANGE PATTERN

The new request has been classified as:
- **Change Type:** {pattern.label_cn} ({pattern.label_en})
- **Category:** {classification.category.value}
- **Confidence:** {classification.confidence.value}
- **Typical Sample Stage:** {classification.sample_stage.value if classification.sample_stage else 'N/A'}

### Pattern Knowledge (from historical analysis):
{pattern_to_prompt_context(pattern)}
"""

        return (
            PATTERN_MIGRATION_SYSTEM_PROMPT
            + "\n\n"
            + ANTI_COPY_RULES
            + "\n\n"
            + pattern_context
            + "\n\n"
            + (
                "Generate only JSON matching the PD-ECR V1 GeneratedDraft schema. "
                "Use exactly these six modules: "
                + ", ".join(module.value for module in PdEcrModuleId)
                + ". Every evidence-backed module must include source_cases or source_files. "
                "If evidence is insufficient, set needs_human_input=true and explain the missing evidence. "
                "Use draft_status=V1_MVP_DRAFT and do not claim production approval.\n"
                "In the applied_patterns field of each module, list which pattern(s) you applied.\n\n"
                f"Input:\n{json.dumps(request.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n\n"
                f"Evidence:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}"
            )
        )

    # --- Legacy prompt (unchanged, kept for backward compatibility) ---
    return (
        "Generate only JSON matching the PD-ECR V1 GeneratedDraft schema. "
        "Use exactly these six modules: "
        + ", ".join(module.value for module in PdEcrModuleId)
        + ". Every evidence-backed module must include source_cases or source_files. "
        "If evidence is insufficient, set needs_human_input=true and explain the missing evidence. "
        "Use draft_status=V1_MVP_DRAFT and do not claim production approval.\n\n"
        f"Input:\n{json.dumps(request.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n\n"
        f"Evidence:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )


def draft_id_for(request: NewPdEcrRequest, similar_cases: list[SimilarCaseResult]) -> str:
    payload = {
        "input": request.model_dump(mode="json"),
        "similar_cases": [item.case_id for item in similar_cases],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"draft-{digest[:16]}"


def parse_generated_draft(payload: str | dict[str, Any]) -> GeneratedDraft:
    if isinstance(payload, str):
        text = payload.strip()
        json_fence = chr(96) * 3 + "json"
        plain_fence = chr(96) * 3
        if text.startswith(json_fence):
            text = text[len(json_fence) :].strip()
        if text.startswith(plain_fence):
            text = text[len(plain_fence) :].strip()
        if text.endswith(plain_fence):
            text = text[: -len(plain_fence)].strip()
        payload = json.loads(text)
    return GeneratedDraft.model_validate(payload)


def generate_grounded_draft(
    data: dict[str, Any],
    *,
    similar_cases: list[dict[str, Any] | SimilarCaseResult] | None = None,
) -> GeneratedDraft:
    if similar_cases is None:
        request, retrieved = retrieve_similar_cases(
            data, top_k=int(data.get("top_k") or 5)
        )
    else:
        request, _ = retrieve_similar_cases(data, top_k=int(data.get("top_k") or 5))
        retrieved = [
            _coerce_similar_case(item, rank=index + 1)
            for index, item in enumerate(similar_cases)
        ]

    # --- Classification for pattern-aware generation ---
    classification: ClassificationResult | None = None
    if _USE_PATTERN_RETRIEVAL:
        try:
            from app.services.pd_ecr_classifier import classify_change_type

            classification = classify_change_type(request)
        except Exception:
            classification = None

    draft_id = draft_id_for(request, retrieved)
    modules = _build_modules(request, retrieved, classification=classification)
    draft = GeneratedDraft(
        draft_id=draft_id,
        draft_status=DraftStatus.V1_MVP_DRAFT,
        input_snapshot=request,
        similar_cases=retrieved,
        modules=modules,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    DRAFT_CACHE[draft.draft_id] = draft
    return draft


def generate_structured_draft(
    data: dict[str, Any],
    *,
    similar_cases: list[dict[str, Any] | SimilarCaseResult] | None = None,
) -> GeneratedDraft:
    return generate_grounded_draft(data, similar_cases=similar_cases)


def get_cached_draft(draft_id: str) -> GeneratedDraft | None:
    return DRAFT_CACHE.get(draft_id)


def _coerce_similar_case(
    item: dict[str, Any] | SimilarCaseResult, *, rank: int
) -> SimilarCaseResult:
    if isinstance(item, SimilarCaseResult):
        return item.model_copy(update={"rank": rank})
    try:
        return SimilarCaseResult.model_validate({**item, "rank": item.get("rank") or rank})
    except ValidationError:
        source_file = str(item.get("source_file") or item.get("source") or "")
        case_id = str(
            item.get("case_id") or item.get("case_no") or source_file or f"case-{rank}"
        )
        return SimilarCaseResult(
            rank=rank,
            case_id=case_id,
            dc_no=str(item.get("dc_no") or ""),
            change_type=str(item.get("change_type") or ""),
            matched_fields=list(item.get("matched_fields") or []),
            similarity_score=float(
                item.get("similarity_score") or item.get("score") or 0
            ),
            similarity_reason=str(item.get("similarity_reason") or ""),
            source_file=source_file or case_id,
            module_summary=str(
                item.get("module_summary") or item.get("text") or case_id
            )[:1000],
        )


def _source_cases(similar_cases: list[SimilarCaseResult]) -> list[str]:
    return [item.case_id for item in similar_cases[:5]]


def _source_files(similar_cases: list[SimilarCaseResult]) -> list[str]:
    result: list[str] = []
    for item in similar_cases:
        for source_file in item.source_files or [item.source_file]:
            if source_file and source_file not in result:
                result.append(source_file)
    return result[:8]


def _evidence_text(
    similar_cases: list[SimilarCaseResult], module_id: PdEcrModuleId
) -> str:
    snippets: list[str] = []
    for item in similar_cases:
        for snippet in item.retrieval_context.evidence_snippets:
            if snippet.module_id in {None, module_id} or module_id.value in snippet.text.lower():
                snippets.append(f"- {item.case_id} / {snippet.source_file}: {snippet.text}")
        if len(snippets) >= 4:
            break
    if not snippets:
        snippets = [
            f"- {item.case_id} / {item.source_file}: {item.module_summary}"
            for item in similar_cases[:3]
        ]
    return "\n".join(snippets)


def _build_modules(
    request: NewPdEcrRequest,
    similar_cases: list[SimilarCaseResult],
    *,
    classification: ClassificationResult | None = None,
) -> list[GeneratedModule]:
    source_cases = _source_cases(similar_cases)
    source_files = _source_files(similar_cases)
    has_evidence = bool(similar_cases)

    # --- Pattern-derived content injection (when flag is on) ---
    pattern_risk_text = ""
    pattern_checklist_text = ""
    pattern_approval_text = ""
    pattern_category = ""
    applied_patterns: list[str] = []

    if _USE_PATTERN_RETRIEVAL and classification is not None:
        if classification.category != ChangeTypeCategory.UNKNOWN:
            pattern = get_pattern(classification.category)
            if pattern:
                pattern_category = classification.category.value
                applied_patterns.append(pattern_category)

                # Build risk profile text for IMPACT_ANALYSIS
                risk_lines = ["## Pattern-based Risk Assessment Framework\n"]
                for area, guidance in pattern.risk_profile.items():
                    risk_lines.append(f"- **{area}**: {guidance}")
                pattern_risk_text = "\n".join(risk_lines)

                # Build checklist text for IMPLEMENTATION_PLAN
                if pattern.checklist_template:
                    cl_lines = ["## Pattern-based Implementation Checklist\n"]
                    for dept, items in pattern.checklist_template.items():
                        cl_lines.append(f"### {dept}")
                        for item in items:
                            cl_lines.append(f"- [ ] {item}")
                    pattern_checklist_text = "\n".join(cl_lines)

                # Build approval text for APPROVAL_SIGNOFF_INFORMATION
                pattern_approval_text = (
                    "## Pattern-based Approval Roles\n"
                    + "\n".join(f"- {role}" for role in pattern.required_approvals)
                )

                # Add implementation guidance
                if pattern.implementation_guidance:
                    pattern_approval_text += (
                        f"\n\n**Guidance:** {pattern.implementation_guidance}"
                    )

                # Add common mistakes to IMPLEMENTATION_PLAN
                if pattern.common_mistakes:
                    pattern_checklist_text += "\n\n### Common Pitfalls to Avoid\n"
                    pattern_checklist_text += "\n".join(
                        f"- ⚠️ {m}" for m in pattern.common_mistakes
                    )

    content_by_module: dict[PdEcrModuleId, str] = {
        PdEcrModuleId.BASIC_INFORMATION: (
            f"Change source: {request.change_source or request.initiator or 'Needs human input'}\n"
            f"Change reason: {request.change_reason}\n"
            f"Change description: {request.change_description}\n"
            f"Current design: {request.current_design or 'Needs human input'}\n"
            f"Change proposal: {request.change_proposal or request.change_description}\n"
            f"Target close date: {request.target_close_date or 'Needs human input'}"
        ),
        PdEcrModuleId.CHANGE_DESCRIPTION: (
            "Draft affection analysis based on similar historical cases. "
            "Review function, performance, interface, reliability, supplier part, "
            "manufacturing, assembly, testing, documents, and customer impact.\n\n"
            + (f"{pattern_risk_text}\n\n" if pattern_risk_text else "")
            + f"Evidence:\n{_evidence_text(similar_cases, PdEcrModuleId.CHANGE_DESCRIPTION)}"
        ),
        PdEcrModuleId.REASON_FOR_CHANGE: (
            "Draft validation and trial run plan: define required validation items, "
            "evaluation criteria, planned finish dates, responsible persons, and comments.\n\n"
            f"Evidence:\n{_evidence_text(similar_cases, PdEcrModuleId.REASON_FOR_CHANGE)}"
        ),
        PdEcrModuleId.IMPACT_ANALYSIS: (
            "Draft validation and trial run result section. Record OK/NOK status, "
            "result evidence, signer, date, and unresolved validation risks.\n\n"
            f"Evidence:\n{_evidence_text(similar_cases, PdEcrModuleId.IMPACT_ANALYSIS)}"
        ),
        PdEcrModuleId.IMPLEMENTATION_PLAN: (
            "Draft implementation task plan: confirm affected documents/BOM/drawings, "
            "define department actions, assign owners, set due dates, and prepare "
            "closure evidence.\n\n"
            + (f"{pattern_checklist_text}\n\n" if pattern_checklist_text else "")
            + f"Evidence:\n{_evidence_text(similar_cases, PdEcrModuleId.IMPLEMENTATION_PLAN)}"
        ),
        PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION: (
            "Draft implementation result section. Track each action as Closed, "
            "Ongoing, or Open, and confirm overdue items before target close.\n\n"
            + (f"{pattern_approval_text}\n\n" if pattern_approval_text else "")
            + f"Reference cases for approval context:\n{_evidence_text(similar_cases, PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION)}"
        ),
    }

    modules: list[GeneratedModule] = []
    for module_id in PdEcrModuleId:
        warnings: list[str] = []
        needs_human_input = not has_evidence
        if module_id == PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION:
            warnings.append(
                "Implementation result status must be confirmed by the PD-ECR owner before closure."
            )
        if not has_evidence:
            warnings.append("No historical evidence was available for this module.")
        modules.append(
            GeneratedModule(
                module_id=module_id,
                title=MODULE_TITLES[module_id],
                summary=_summary_for(module_id, has_evidence),
                content=content_by_module[module_id],
                source_cases=source_cases if has_evidence else [],
                source_files=source_files if has_evidence else [],
                needs_human_input=needs_human_input,
                warnings=warnings,
                applied_patterns=applied_patterns if has_evidence else [],
            )
        )
    return modules


def _summary_for(module_id: PdEcrModuleId, has_evidence: bool) -> str:
    evidence_note = (
        "with historical source references"
        if has_evidence
        else "needs human input because no evidence was found"
    )
    return f"{MODULE_TITLES[module_id]} draft {evidence_note}."
