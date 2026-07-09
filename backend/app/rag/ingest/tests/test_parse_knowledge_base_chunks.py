from __future__ import annotations

import json
from pathlib import Path

from app.rag.ingest import parse


def test_load_documents_includes_standardized_knowledge_base_chunks(
    tmp_path: Path, monkeypatch
) -> None:
    chunks_path = tmp_path / "knowledge_base" / "chunks" / "chunks.jsonl"
    chunks_path.parent.mkdir(parents=True)
    chunks_path.write_text(
        json.dumps(
            {
                "chunk_id": "CASE-001::impact_analysis",
                "case_id": "CASE-001",
                "chunk_type": "impact_analysis",
                "text": "影响分析: BOM 和验证计划需要同步更新。",
                "metadata": {
                    "case_id": "CASE-001",
                    "source_file": "CASE-001.md",
                    "dc_no": "PDECR24_001",
                    "mcr_no": "MCR-001",
                    "chunk_type": "impact_analysis",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(parse, "KNOWLEDGE_DIR", tmp_path / "missing_knowledge")
    monkeypatch.setattr(parse, "JIE_JIM_DIR", tmp_path / "missing_jie_jim")
    monkeypatch.setattr(parse, "DOCLING_DIR", tmp_path / "missing_docling")
    monkeypatch.setattr(parse, "KNOWLEDGE_BASE_CHUNKS_PATH", chunks_path)

    docs = parse.load_documents()

    assert len(docs) == 1
    doc = docs[0]
    assert doc["source"] == "CASE-001.md"
    assert doc["case_id"] == "CASE-001"
    assert doc["chunk_type"] == "impact_analysis"
    assert doc["metadata"]["dc_no"] == "PDECR24_001"
    assert "standardized PD-ECR knowledge base chunk" in doc["text"]
    assert "BOM" in doc["text"]
