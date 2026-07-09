from __future__ import annotations

from app.rag.ingestion.chunker import build_chunks
from app.rag.schemas.pdecr_case_schema import (
    PdecrCase,
    PdecrMetadata,
    PdecrModules,
    PdecrTask,
    SourceInfo,
)

_META_KEYS = {
    "case_id",
    "dc_no",
    "mcr_no",
    "customer_project",
    "affected_product_no",
    "component_no",
    "source_file",
    "file_type",
    "chunk_type",
}


def _case() -> PdecrCase:
    return PdecrCase(
        case_id="PDECR_24_093",
        source=SourceInfo(source_file="PDECR24_093.pdf", file_type="pdf"),
        metadata=PdecrMetadata(
            dc_no="24_093",
            mcr_no="MCR-1",
            customer_project=["JIM-493"],
            affected_product_no=["P-1"],
            component_no=["C-1"],
        ),
        modules=PdecrModules(
            change_reason="首次样件释放",
            change_proposal="释放 A 样件",
            impact_analysis="对成本无影响",
        ),
        tasks=[PdecrTask(task_name="Trial run", owner="张三", status="done")],
    )


def test_chunker_generates_module_chunks() -> None:
    chunks = build_chunks(_case())
    types = {c.chunk_type for c in chunks}

    # basic_info + 三个模块 + task
    assert "basic_info" in types
    assert "change_reason" in types
    assert "change_proposal" in types
    assert "impact_analysis" in types
    assert "task" in types
    # 未填模块不应生成 chunk
    assert "risk_analysis" not in types


def test_every_chunk_has_full_metadata() -> None:
    for c in build_chunks(_case()):
        assert _META_KEYS.issubset(c.metadata.keys()), c.metadata
        assert c.metadata["chunk_type"] == c.chunk_type
        assert c.metadata["case_id"] == "PDECR_24_093"
        assert c.chunk_id.startswith("PDECR_24_093")
        assert c.text.strip()
