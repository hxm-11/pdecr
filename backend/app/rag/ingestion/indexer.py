"""知识库索引层：先落地本地 JSONL chunk 索引，后续可平滑换 Chroma / FAISS / pgvector。

- 每个 chunk 一行 JSON，写到 knowledge_base/chunks/chunks.jsonl。
- index_case(case)：为一个 case 建 chunk 并写入（同 case 会先删旧行，支持 reindex）。
- search_similar(query, filters, top_k)：相似案例检索占位。
  若已建好向量库（app.rag.retrieval.retrieve_cases 可用）则委托它，并按 filters
  在 chunk metadata 上做过滤；否则退化为对 chunks.jsonl 的关键词打分。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.rag.schemas.pdecr_case_schema import PdecrCase

from .chunker import Chunk, build_chunks

_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
CHUNKS_PATH = _KB_DIR / "chunks" / "chunks.jsonl"


def _read_all() -> list[dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _write_all(rows: list[dict[str, Any]]) -> None:
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def save_chunks(chunks: list[Chunk], *, case_id: str | None = None) -> int:
    """写 chunks 到 JSONL。给了 case_id 就先剔除该 case 的旧行（幂等 reindex）。"""
    existing = _read_all()
    if case_id is not None:
        existing = [r for r in existing if r.get("case_id") != case_id]
    existing.extend(c.to_dict() for c in chunks)
    _write_all(existing)
    return len(chunks)


def index_case(case: PdecrCase, markdown: str | None = None) -> list[Chunk]:
    """为一个标准 case 建 chunk 并写入本地索引，返回 chunk 列表。"""
    chunks = build_chunks(case, markdown)
    save_chunks(chunks, case_id=case.case_id)
    return chunks


def _matches(meta: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, want in filters.items():
        val = meta.get(key)
        if isinstance(val, list):
            if want not in val:
                return False
        elif val != want:
            return False
    return True


def search_similar(
    query: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """相似案例检索占位。

    优先委托已建好的向量检索（retrieve_cases）；不可用时退化为 JSONL 上的
    关键词重叠打分。返回 [{chunk_id, case_id, chunk_type, text, score, metadata}]。
    """
    filters = filters or {}

    # 1) 优先走既有向量检索层（若向量库已构建）
    try:
        from app.rag.retrieval import retrieve_cases

        hits = retrieve_cases({"reason": query}, top_k=top_k * 3)
        results = []
        for h in hits:
            meta = h.metadata or {}
            if filters and not _matches(meta, filters):
                continue
            results.append(
                {
                    "chunk_id": h.chunk_id,
                    "case_id": meta.get("case_id", ""),
                    "chunk_type": meta.get("chunk_type", ""),
                    "text": h.text,
                    "score": h.score,
                    "metadata": meta,
                }
            )
            if len(results) >= top_k:
                break
        if results:
            return results
    except Exception:
        pass  # 向量库未就绪，走本地回退

    # 2) 回退：JSONL 关键词重叠
    q_tokens = {t for t in _tokenize(query) if t}
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in _read_all():
        if filters and not _matches(row.get("metadata", {}), filters):
            continue
        tokens = set(_tokenize(row.get("text", "")))
        if not tokens:
            continue
        overlap = len(q_tokens & tokens) / (len(q_tokens) or 1)
        if overlap > 0:
            scored.append((overlap, {**row, "score": round(overlap, 4)}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]


def _tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[A-Za-z0-9]+|[一-鿿]", text.lower())
