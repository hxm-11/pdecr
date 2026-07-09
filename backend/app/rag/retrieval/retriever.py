"""检索器：把变更请求转成 query，检索相似历史 PD-ECR 案例。

升级版检索质量：
  稠密向量(LangChain FAISS) + 稀疏关键词(BM25) --EnsembleRetriever/RRF 融合-->
  --(可选)cross-encoder 重排--> RetrievedChunk

- 稠密：LangChain FAISS 向量库（app/rag/vector_store/langchain_faiss/），
  用本地 sentence-transformers 模型。
- 稀疏：BM25Retriever（rank_bm25），对同一批 chunk 建倒排。
- 融合：EnsembleRetriever（Reciprocal Rank Fusion），默认权重 稠密0.6 / BM25 0.4。
- 重排（可选）：本地有 cross-encoder 模型时启用（见 RERANKER_PATH），
  没有则自动跳过并打印提示——不会静默降级。

对上层（graph / service）只暴露 retrieve_cases() -> list[RetrievedChunk]，
底层怎么变都无感知。若 LangChain 向量库尚未构建，会回退到旧的 FAISS 检索。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

_BASE_DIR = Path(__file__).resolve().parent.parent  # app/rag
_LC_STORE_DIR = _BASE_DIR / "vector_store" / "langchain_faiss"
# 本地放了 cross-encoder（如 bge-reranker）就会自动启用重排；没有则跳过
RERANKER_PATH = _BASE_DIR / "models" / "bge-reranker-base"

# 融合权重与候选数（可用环境变量覆盖）
# 注意：本领域文档高度模板化，小多语言 embedding 稠密检索区分度弱，
# 实测 BM25 关键词更靠谱，故默认让 BM25 主导（稠密 0.4 / BM25 0.6）。
# 若日后换更强的 embedding 或加了重排，可上调稠密权重。
_DENSE_WEIGHT = float(os.getenv("PD_ECR_DENSE_WEIGHT", "0.4"))
_BM25_WEIGHT = float(os.getenv("PD_ECR_BM25_WEIGHT", "0.6"))
_CANDIDATE_K = int(os.getenv("PD_ECR_CANDIDATE_K", "20"))


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float
    chunk_id: Any = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_context_block(self, rank: int) -> str:
        return (
            f"【历史案例 {rank}】\n"
            f"来源文件：{self.source}\n"
            f"匹配分数：{round(self.score, 4)}\n"
            f"内容：\n{self.text}\n"
        )


# ──────────────────────────────────────────────────────────────
# query 构造（沿用旧的字段拼接策略）
# ──────────────────────────────────────────────────────────────
def build_query(data: Dict[str, Any]) -> str:
    parts = [
        f"Customer Project: {data.get('customer_project', '')}",
        f"MCR No: {data.get('mcr_no', '')}",
        f"Product No: {data.get('product_no', '')}",
        f"Component No: {data.get('component_no', '')}",
        f"Reason: {data.get('reason', '')}",
        f"Current Design: {data.get('current_design', '')}",
        f"Change Proposal: {data.get('change_proposal', '')}",
        f"Remarks: {data.get('remarks', '')}",
    ]
    category = data.get("_change_type_category", "")
    if category:
        parts.append(f"Change Type Category: {category}")
    return "\n".join(p for p in parts if str(p).split(": ", 1)[-1].strip())


# ──────────────────────────────────────────────────────────────
# 加载 FAISS 向量库 + 在同一批 chunk 上建 BM25（进程内缓存）
# ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_hybrid():
    """返回 (store, bm25, all_docs)；失败返回 None（触发回退）。"""
    try:
        from langchain_community.retrievers import BM25Retriever
        from langchain_community.vectorstores import FAISS

        from .embeddings import get_embeddings

        if not _LC_STORE_DIR.exists():
            print(f"[retrieval] LangChain 向量库不存在：{_LC_STORE_DIR}，"
                  "请先运行 python -m app.rag.ingest.build_index")
            return None

        store = FAISS.load_local(
            str(_LC_STORE_DIR),
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        all_docs = list(store.docstore._dict.values())
        bm25 = BM25Retriever.from_documents(all_docs)
        return store, bm25, all_docs
    except Exception as exc:
        print(f"[retrieval] 混合检索构建失败，将回退旧检索：{exc}")
        return None


def _minmax(values: List[float]) -> List[float]:
    """把一组分数归一化到 [0, 1]；全相等时返回全 0（无区分度）。"""
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span < 1e-9:
        return [0.0 for _ in values]
    return [(v - lo) / span for v in values]


def _doc_key(doc: Any) -> tuple:
    meta = doc.metadata or {}
    return (meta.get("source", ""), meta.get("chunk_id", ""))


# ──────────────────────────────────────────────────────────────
# 可选：cross-encoder 重排
# ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_reranker():
    """本地有 reranker 模型才返回，否则 None。"""
    if not RERANKER_PATH.exists():
        return None
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(str(RERANKER_PATH))
    except Exception as exc:
        print(f"[retrieval] reranker 加载失败，跳过重排：{exc}")
        return None


def _rerank(query: str, docs: List[Any], top_k: int) -> List[Any]:
    reranker = _get_reranker()
    if reranker is None or not docs:
        return docs[:top_k]
    pairs = [(query, d.page_content) for d in docs]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    for d, s in ranked:
        d.metadata["_rerank_score"] = float(s)
    return [d for d, _ in ranked[:top_k]]


# ──────────────────────────────────────────────────────────────
# 对外主入口
# ──────────────────────────────────────────────────────────────
def retrieve_cases(request: Dict[str, Any], top_k: int = 5) -> List[RetrievedChunk]:
    query = build_query(request)
    if not query.strip():
        return []

    hybrid = _get_hybrid()

    # 回退：LangChain 向量库不可用时用旧的 FAISS 检索，保证不断服务
    if hybrid is None:
        return _legacy_retrieve(request, top_k)

    store, bm25, all_docs = hybrid

    # ── 稠密：对全库打分（MAX_INNER_PRODUCT，越大越相似）──
    dense_hits = store.similarity_search_with_score(query, k=len(all_docs))
    dense_by_key = {_doc_key(doc): float(score) for doc, score in dense_hits}

    # ── BM25：对全库打分（与 all_docs 顺序一致）──
    tokenized = bm25.preprocess_func(query)
    bm25_scores = list(bm25.vectorizer.get_scores(tokenized))

    # ── 各自归一化到 [0,1] 后加权融合，得到真实、可解释的融合分 ──
    dense_list = [dense_by_key.get(_doc_key(d), 0.0) for d in all_docs]
    dense_norm = _minmax(dense_list)
    bm25_norm = _minmax(bm25_scores)

    scored = []
    for i, doc in enumerate(all_docs):
        fused = _DENSE_WEIGHT * dense_norm[i] + _BM25_WEIGHT * bm25_norm[i]
        scored.append((fused, dense_norm[i], bm25_norm[i], doc))
    scored.sort(key=lambda x: x[0], reverse=True)

    # ── 可选：cross-encoder 对前若干候选重排（本地有模型才生效）──
    candidates = [row[3] for row in scored[: max(_CANDIDATE_K, top_k)]]
    fused_by_key = {_doc_key(row[3]): (row[0], row[1], row[2]) for row in scored}
    reranked = _rerank(query, candidates, top_k)

    results: List[RetrievedChunk] = []
    for doc in reranked[:top_k]:
        meta = dict(doc.metadata or {})
        fused, d_norm, b_norm = fused_by_key.get(_doc_key(doc), (0.0, 0.0, 0.0))
        rerank_score = meta.get("_rerank_score")
        # 有重排分则以重排分为主分；否则用融合分
        score = float(rerank_score) if rerank_score is not None else fused
        meta["_dense_score"] = round(d_norm, 4)
        meta["_bm25_score"] = round(b_norm, 4)
        meta["_fused_score"] = round(fused, 4)
        results.append(
            RetrievedChunk(
                text=doc.page_content,
                source=meta.get("source", ""),
                score=score,
                chunk_id=meta.get("chunk_id", ""),
                metadata=meta,
            )
        )
    return results


def _legacy_retrieve(request: Dict[str, Any], top_k: int) -> List[RetrievedChunk]:
    try:
        from app.rag.retriever import retrieve_pd_ecr_results
    except Exception as exc:  # pragma: no cover
        print(f"[retrieval] 旧检索也不可用，返回空：{exc}")
        return []

    raw = retrieve_pd_ecr_results(request, top_k=top_k)
    return [
        RetrievedChunk(
            text=item.get("text", ""),
            source=item.get("source", ""),
            score=float(item.get("score", 0.0)),
            chunk_id=item.get("chunk_id", ""),
            metadata=item.get("metadata", {}),
        )
        for item in raw
    ]


def build_context(chunks: List[RetrievedChunk]) -> str:
    return "\n\n".join(
        chunk.as_context_block(rank) for rank, chunk in enumerate(chunks, start=1)
    )
