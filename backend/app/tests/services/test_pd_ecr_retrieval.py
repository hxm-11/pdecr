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


def test_retrieve_returns_v1_similar_case_results():
    request, results = retrieve_similar_cases(VALID_INPUT, top_k=3)

    assert request.top_k == 3
    assert results
    assert len(results) <= 3
    first = results[0]
    assert first.case_id
    assert first.source_file
    assert first.source_files
    assert first.source_cases
    assert first.module_summary
