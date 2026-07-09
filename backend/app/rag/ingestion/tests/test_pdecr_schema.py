from __future__ import annotations

from pathlib import Path

from app.rag.schemas.pdecr_case_schema import (
    PdecrCase,
    PdecrMetadata,
    PdecrModules,
    SourceInfo,
    validate_case,
)


def _sample_case() -> PdecrCase:
    return PdecrCase(
        case_id="PDECR_24_093",
        source=SourceInfo(
            source_file="PDECR24_093.pdf", file_type="pdf", parser="mineru"
        ),
        metadata=PdecrMetadata(
            dc_no="24_093",
            date="2024-09-03",
            customer_project=["JIM-493"],
            affected_product_no=["F01ZH003FU-01"],
            component_no=["C-01"],
        ),
        modules=PdecrModules(
            change_reason="首次样件释放",
            change_proposal="释放 A 样件",
        ),
    )


def test_schema_can_save_and_load_case(tmp_path: Path) -> None:
    case = _sample_case()
    out = tmp_path / "case.json"
    case.save(str(out))

    assert out.exists()
    loaded = PdecrCase.load(str(out))

    assert loaded.case_id == case.case_id
    assert loaded.metadata.dc_no == "24_093"
    assert loaded.metadata.customer_project == ["JIM-493"]
    assert loaded.modules.change_reason == "首次样件释放"
    # 往返一致
    assert loaded.model_dump() == case.model_dump()


def test_validate_case_reports_missing_fields() -> None:
    empty = PdecrCase(case_id="X")
    report = validate_case(empty)
    assert "metadata.dc_no" in report["missing_fields"]
    assert "no module content extracted" in report["warnings"]

    filled = _sample_case()
    report2 = validate_case(filled)
    assert "metadata.dc_no" not in report2["missing_fields"]
    assert "change_reason" in report2["filled_modules"]
