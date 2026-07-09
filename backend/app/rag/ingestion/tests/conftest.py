"""把知识库写入路径重定向到临时目录，避免污染真实 knowledge_base。

同时强制走 rule-based 抽取（清空 LLM_API_KEY），让测试无需网络/密钥即可跑。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.rag.ingestion import indexer, pipeline

    cases = tmp_path / "cases"
    markdown = tmp_path / "markdown"
    chunks = tmp_path / "chunks" / "chunks.jsonl"
    for d in (cases, markdown, chunks.parent):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(pipeline, "CASES_DIR", cases)
    monkeypatch.setattr(pipeline, "MARKDOWN_DIR", markdown)
    monkeypatch.setattr(indexer, "CHUNKS_PATH", chunks)

    # 无 LLM，强制 rule-based，保证离线可测
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    return tmp_path
