from __future__ import annotations

from pathlib import Path

from app.rag.ingestion import pipeline
from app.rag.ingestion.registry import STATUS_INDEXED, Registry

_MD = "# PDECR24_300\n变更原因: 材料变更\n变更方案: 改用新供应商材料\n"


def test_registry_avoids_duplicate_ingestion(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "PDECR24_300.md").write_text(_MD, encoding="utf-8")

    reg = Registry(path=tmp_path / "registry.json")

    first = pipeline.ingest_case_directory(str(raw_dir), "mineru", registry=reg)
    assert len(first) == 1
    entry = reg.get(str(raw_dir / "PDECR24_300.md"))
    assert entry is not None and entry.status == STATUS_INDEXED

    # 第二次同文件、同内容 -> 跳过，不重复入库
    second = pipeline.ingest_case_directory(str(raw_dir), "mineru", registry=reg)
    assert second == []


def test_registry_reindexes_on_content_change(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    f = raw_dir / "PDECR24_301.md"
    f.write_text(_MD, encoding="utf-8")

    reg = Registry(path=tmp_path / "registry.json")
    assert (
        len(pipeline.ingest_case_directory(str(raw_dir), "mineru", registry=reg)) == 1
    )

    # 内容变化 -> checksum 变 -> 允许 reindex
    f.write_text(_MD + "\n备注: 补充说明\n", encoding="utf-8")
    assert (
        len(pipeline.ingest_case_directory(str(raw_dir), "mineru", registry=reg)) == 1
    )
