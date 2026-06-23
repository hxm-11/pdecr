import pytest
from pydantic import ValidationError

from app.services.pd_ecr_schema import (
    BasicReportExport,
    DraftStatus,
    ExportFormat,
    GeneratedDraft,
    GeneratedModule,
    HistoricalCase,
    HistoricalMetadata,
    HistoricalModule,
    NewPdEcrRequest,
    PdEcrModuleId,
    SimilarCaseResult,
    get_required_metadata_keys,
    get_v1_module_ids,
    normalize_new_pd_ecr_input,
)


def valid_request() -> NewPdEcrRequest:
    return NewPdEcrRequest(
        dc_no="DC-001",
        mcr_no="MCR-001",
        customer_project="JIM-493",
        product_no="F01ZH003G1-00",
        part_no="F01ZH003G1-00",
        change_type="A Sample release",
        change_description="Release detachable DOC+SDPF sample parts",
        change_reason="Customer request and design optimization",
    )


def valid_similar_case() -> SimilarCaseResult:
    return SimilarCaseResult(
        rank=1,
        case_id="PDECR24_093",
        dc_no="24_093",
        change_type="A Sample release",
        matched_fields=["customer_project", "product_no"],
        similarity_score=0.91,
        source_file="PDECR24_093_Change.md",
        module_summary="Historical A sample release for JIM-493.",
    )


def generated_modules() -> list[GeneratedModule]:
    return [
        GeneratedModule(
            module_id=module_id,
            title=title,
            summary=f"{title} summary",
            content=f"{title} content",
            source_cases=["PDECR24_093"],
            source_files=["PDECR24_093_Change.md"],
        )
        for module_id, title in [
            (PdEcrModuleId.BASIC_INFORMATION, "Change Request description"),
            (PdEcrModuleId.CHANGE_DESCRIPTION, "Affection analysis"),
            (PdEcrModuleId.REASON_FOR_CHANGE, "Validation &trial run plan"),
            (
                PdEcrModuleId.IMPACT_ANALYSIS,
                "Validation &Trial run plan result",
            ),
            (PdEcrModuleId.IMPLEMENTATION_PLAN, "Implementation task plan"),
            (PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION, "Implementation result"),
        ]
    ]


def test_required_metadata_keys_match_v1_standard():
    assert get_required_metadata_keys() == (
        "case_id",
        "dc_no",
        "mcr_no",
        "change_type",
        "product_no",
        "part_no",
        "customer_project",
        "source_file",
    )


def test_v1_module_ids_are_the_six_required_modules():
    assert get_v1_module_ids() == (
        PdEcrModuleId.BASIC_INFORMATION,
        PdEcrModuleId.CHANGE_DESCRIPTION,
        PdEcrModuleId.REASON_FOR_CHANGE,
        PdEcrModuleId.IMPACT_ANALYSIS,
        PdEcrModuleId.IMPLEMENTATION_PLAN,
        PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION,
    )


def test_v1_module_titles_match_pd_ecr_page_sections():
    from app.services.pd_ecr_schema import MODULE_TITLES

    assert [MODULE_TITLES[module_id] for module_id in get_v1_module_ids()] == [
        "Change Request description",
        "Affection analysis",
        "Validation &trial run plan",
        "Validation &Trial run plan result",
        "Implementation task plan",
        "Implementation result",
    ]


def test_legacy_input_aliases_map_to_v1_request_fields():
    raw = {
        "dc_no": "DC-001",
        "mcr_no": "MCR-001",
        "customer_project": "JIM-493",
        "product_no": "F01ZH003G1-00",
        "component_no": "F01ZH003G1-00",
        "change_type": "A Sample release",
        "change_proposal": "Release detachable DOC+SDPF sample parts",
        "reason": "Customer request and design optimization",
    }

    normalized = normalize_new_pd_ecr_input(raw)
    request = NewPdEcrRequest.from_legacy_input(raw)

    assert normalized["part_no"] == raw["component_no"]
    assert normalized["change_reason"] == raw["reason"]
    assert request.part_no == raw["component_no"]
    assert request.change_reason == raw["reason"]
    assert request.change_description == raw["change_proposal"]
    assert request.top_k == 5


def test_lightweight_rag_input_accepts_three_user_signals():
    raw = {
        "source": "Purchasing",
        "reason": "RPP cost reduction",
        "change_description": "Use a second supplier bolt with unchanged material.",
        "target_close_date": "2026-07-03",
    }

    normalized = normalize_new_pd_ecr_input(raw)
    request = NewPdEcrRequest.from_legacy_input(raw)

    assert normalized["change_source"] == "Purchasing"
    assert normalized["change_reason"] == "RPP cost reduction"
    assert request.change_source == "Purchasing"
    assert request.change_reason == "RPP cost reduction"
    assert request.change_description == raw["change_description"]
    assert request.target_close_date == "2026-07-03"
    assert request.dc_no == ""


def test_historical_case_allows_missing_metadata_but_keeps_required_keys_present():
    metadata = HistoricalMetadata(
        case_id="PDECR24_093",
        dc_no="24_093",
        mcr_no="",
        change_type="",
        product_no="F01ZH003G1-00",
        part_no="F01ZH003G1-00",
        customer_project=["JIM-493"],
        source_file="PDECR24_093_Change.md",
    )
    module = HistoricalModule(
        module_id=PdEcrModuleId.CHANGE_DESCRIPTION,
        title="Change Description",
        summary="Historical summary",
        content="Historical content",
        source_file="PDECR24_093_Change.md",
    )

    case = HistoricalCase(
        case_id="PDECR24_093",
        metadata=metadata,
        modules={module.module_id: module},
        source_file="PDECR24_093_Change.md",
        missing_fields=["mcr_no", "change_type"],
    )

    assert case.metadata.customer_project == ["JIM-493"]
    assert case.missing_fields == ["mcr_no", "change_type"]
    assert case.modules[PdEcrModuleId.CHANGE_DESCRIPTION].source_file == (
        "PDECR24_093_Change.md"
    )


def test_historical_case_rejects_mismatched_metadata_identity():
    metadata = HistoricalMetadata(
        case_id="PDECR24_093",
        source_file="PDECR24_093_Change.md",
    )

    with pytest.raises(ValidationError):
        HistoricalCase(
            case_id="OTHER",
            metadata=metadata,
            source_file="PDECR24_093_Change.md",
        )


def test_similar_case_result_preserves_source_case_and_file_references():
    result = valid_similar_case()

    assert result.source_cases == ["PDECR24_093"]
    assert result.source_files == ["PDECR24_093_Change.md"]


def test_generated_draft_requires_exactly_six_v1_modules():
    draft = GeneratedDraft(
        draft_id="draft-001",
        input_snapshot=valid_request(),
        similar_cases=[valid_similar_case()],
        modules=generated_modules(),
        generated_at="2026-06-16T00:00:00Z",
    )

    assert draft.draft_status == DraftStatus.V1_MVP_DRAFT
    assert len(draft.modules) == 6

    with pytest.raises(ValidationError):
        GeneratedDraft(
            draft_id="draft-002",
            input_snapshot=valid_request(),
            modules=generated_modules()[:-1],
            generated_at="2026-06-16T00:00:00Z",
        )


def test_basic_report_export_uses_v1_draft_status_and_source_files():
    export = BasicReportExport(
        export_id="export-001",
        draft_id="draft-001",
        format=ExportFormat.HTML,
        draft_status=DraftStatus.V1_MVP_DRAFT,
        input_snapshot=valid_request(),
        similar_cases=[valid_similar_case()],
        modules=generated_modules(),
        source_files=["PDECR24_093_Change.md"],
        created_at="2026-06-16T00:00:00Z",
    )

    assert export.format == ExportFormat.HTML
    assert export.draft_status == DraftStatus.V1_MVP_DRAFT
    assert export.source_files == ["PDECR24_093_Change.md"]
