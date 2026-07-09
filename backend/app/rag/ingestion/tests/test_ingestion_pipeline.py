from __future__ import annotations

import json
from pathlib import Path

from app.rag.ingestion import indexer, pipeline

_MINIMAL_MD = """# PDECR24_200 test

变更原因: 客户要求增加倒角避免压装卡滞
变更方案: 回油口增加 C 角 1x45° 和圆角 R1
"""


def test_pipeline_handles_missing_fields(tmp_path: Path) -> None:
    md_path = tmp_path / "PDECR24_200.md"
    md_path.write_text(_MINIMAL_MD, encoding="utf-8")

    case = pipeline.ingest_mineru_case(None, str(md_path), "PDECR24_200.md")

    # case_id 稳定生成（dc_no 来自文件名/正文）
    assert case.case_id
    # 抽不到的字段是 None/[]，不是编造值
    assert case.metadata.mcr_no is None
    assert case.metadata.customer_project == []
    # 抽到的模块进入正文
    assert case.modules.change_reason and "客户要求" in case.modules.change_reason
    # quality_control 记录了缺失字段并标记需人工复核
    assert case.quality_control.missing_fields
    assert case.quality_control.needs_human_review is True

    # 落地文件都生成了
    assert (pipeline.CASES_DIR / f"{case.case_id}.json").exists()
    assert (pipeline.MARKDOWN_DIR / f"{case.case_id}.md").exists()
    assert indexer.CHUNKS_PATH.exists()

    # chunks.jsonl 每行合法且带 metadata
    rows = [
        json.loads(ln)
        for ln in indexer.CHUNKS_PATH.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert rows
    assert all("metadata" in r and r["metadata"].get("chunk_type") for r in rows)


def test_pipeline_does_not_crash_on_empty_markdown(tmp_path: Path) -> None:
    md_path = tmp_path / "empty.md"
    md_path.write_text("   \n  \n", encoding="utf-8")

    case = pipeline.ingest_mineru_case(None, str(md_path), "empty.md")
    # 完全抽不到 -> failed，但不抛异常
    assert case.quality_control.extraction_status in {"failed", "partial"}
