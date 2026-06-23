from app.services.pd_ecr_case_loader import (
    case_to_detail,
    case_to_list_item,
    find_historical_case,
    load_historical_cases,
)


def test_loader_returns_v1_historical_cases_with_missing_fields():
    cases = load_historical_cases(limit=5)

    assert cases
    first = cases[0]
    assert first.case_id
    assert first.metadata.case_id == first.case_id
    assert first.source_file
    assert isinstance(first.missing_fields, list)


def test_case_list_item_keeps_v1_and_legacy_fields():
    case = load_historical_cases(limit=1)[0]
    item = case_to_list_item(case)

    assert item["case_id"] == case.case_id
    assert item["metadata"]["case_id"] == case.case_id
    assert "missing_fields" in item
    assert item["case_no"] == case.case_id
    assert "part_number" in item


def test_find_case_resolves_by_case_id_and_detail_has_modules():
    case = load_historical_cases(limit=2)[0]
    resolved = find_historical_case(case.case_id)

    assert resolved is not None
    assert resolved.case_id == case.case_id

    detail = case_to_detail(resolved)
    assert detail["case_id"] == case.case_id
    assert len(detail["modules"]) == 6
    assert detail["case"]["case_no"] == case.case_id
