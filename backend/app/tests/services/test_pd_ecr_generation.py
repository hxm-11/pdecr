from app.services.pd_ecr_export import export_v1_draft
from app.services.pd_ecr_generation import generate_grounded_draft, get_cached_draft
from app.services.pd_ecr_retrieval import retrieve_similar_cases


VALID_INPUT = {
    "dc_no": "PD-ECR-DEMO-001",
    "mcr_no": "MCR-DEMO-001",
    "customer_project": "JIM-493",
    "product_no": "F01ZH003G1-00",
    "part_no": "F01ZH003G1-00",
    "change_type": "A Sample release",
    "change_description": "Release detachable and integrated DOC+SDPF sample parts",
    "change_reason": "Customer request and design optimization",
}


def test_generate_grounded_draft_has_six_v1_modules_and_sources():
    _, similar_cases = retrieve_similar_cases(VALID_INPUT, top_k=2)
    draft = generate_grounded_draft(
        VALID_INPUT,
        similar_cases=[case.model_dump(mode="json") for case in similar_cases],
    )

    assert draft.draft_status == "V1_MVP_DRAFT"
    assert len(draft.modules) == 6
    assert get_cached_draft(draft.draft_id) is not None
    sourced_modules = [
        module for module in draft.modules if module.source_cases or module.source_files
    ]
    assert sourced_modules


def test_export_v1_draft_writes_demo_report_with_sources():
    _, similar_cases = retrieve_similar_cases(VALID_INPUT, top_k=1)
    draft = generate_grounded_draft(
        VALID_INPUT,
        similar_cases=[case.model_dump(mode="json") for case in similar_cases],
    )
    export = export_v1_draft(draft_id=draft.draft_id, export_format="html")

    assert export.draft_id == draft.draft_id
    assert export.draft_status == "V1_MVP_DRAFT"
    assert export.download_url.endswith(".html")
    assert export.source_files
