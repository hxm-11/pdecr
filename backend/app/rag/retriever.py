import pickle
import re
from pathlib import Path
from typing import Dict, Any, List

try:
    import numpy as np
except ImportError:
    np = None

try:
    import faiss
except ImportError:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


BASE_DIR = Path(__file__).resolve().parent

VECTOR_DIR = BASE_DIR / "vector_store"
FAISS_PATH = VECTOR_DIR / "pd_ecr.faiss"
META_PATH = VECTOR_DIR / "pd_ecr_meta.pkl"

MODEL_PATH = BASE_DIR / "models" / "paraphrase-multilingual-MiniLM-L12-v2"


_model = None
_index = None
_meta = None


def get_model() -> SentenceTransformer:
    global _model

    if _model is None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not installed")

        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"本地 sentence-transformers 模型不存在：{MODEL_PATH}"
            )

        _model = SentenceTransformer(str(MODEL_PATH))

    return _model


def load_faiss_index():
    global _index, _meta

    if _index is not None and _meta is not None:
        return _index, _meta

    if faiss is None:
        raise RuntimeError("faiss is not installed")

    if not FAISS_PATH.exists():
        raise RuntimeError(
            f"FAISS 索引文件不存在：{FAISS_PATH}，请先运行 python -m app.rag.ingest.build_index"
        )

    if not META_PATH.exists():
        raise RuntimeError(
            f"FAISS 元数据文件不存在：{META_PATH}，请先运行 python -m app.rag.ingest.build_index"
        )

    _index = faiss.read_index(str(FAISS_PATH))

    with open(META_PATH, "rb") as f:
        _meta = pickle.load(f)

    return _index, _meta


def build_query_from_input(data: Dict[str, Any]) -> str:
    parts = [
        f"Customer Project: {data.get('customer_project', '')}",
        f"MCR No: {data.get('mcr_no', '')}",
        f"Product No: {data.get('product_no', '')}",
        f"Component No: {data.get('component_no', '')}",
        f"Initiator: {data.get('initiator', '')}",
        f"Reason: {data.get('reason', '')}",
        f"Current Design: {data.get('current_design', '')}",
        f"Change Proposal: {data.get('change_proposal', '')}",
        f"Remarks: {data.get('remarks', '')}",
    ]

    # When pattern-based retrieval is active, include the classified change type
    # as an additional semantic signal for FAISS search
    category = data.get("_change_type_category", "")
    if category:
        parts.append(f"Change Type Category: {category}")

    parts.append(
        "PD-ECR impact analysis implementation checklist quality validation BOM drawing test report approval"
    )

    return "\n".join([p for p in parts if str(p).strip()])


def _read_knowledge_documents() -> List[Dict[str, Any]]:
    knowledge_dir = BASE_DIR / "knowledge"
    docs = []

    if not knowledge_dir.exists():
        return docs

    for file_path in knowledge_dir.rglob("*"):
        if file_path.suffix.lower() not in [".md", ".txt", ".json"]:
            continue

        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue

        if text:
            docs.append({"source": file_path.name, "chunk_id": 0, "text": text})

    return docs


def _query_terms(query: str) -> List[str]:
    terms = re.split(r"[\s,;:，。；：/\\|()\[\]{}<>\"']+", str(query).lower())
    return [term for term in terms if len(term) >= 2]


KEYWORD_STOP_TERMS = {
    "pd-ecr",
    "pdecr",
    "impact",
    "implementation",
    "quality",
    "approval",
    "drawing",
    "fmea",
    "validation",
    "verification",
    "bom",
    "change",
    "report",
    "test",
}


def _keyword_score(text: str, terms: List[str]) -> float:
    lower_text = str(text or "").lower()
    score = 0.0

    for term in terms:
        if term in lower_text:
            score += 1.0

    for important in [
        "pd-ecr",
        "pdecr",
        "impact",
        "implementation",
        "quality",
        "approval",
        "drawing",
        "fmea",
        "validation",
        "verification",
        "bom",
        "change",
    ]:
        if important in lower_text:
            score += 0.2

    return score


def build_keyword_query_from_input(data: Dict[str, Any]) -> str:
    values = [
        data.get("customer_project", ""),
        data.get("mcr_no", ""),
        data.get("product_no", ""),
        data.get("component_no", ""),
        data.get("reason", ""),
        data.get("current_design", ""),
        data.get("change_proposal", ""),
        data.get("remarks", ""),
    ]

    return "\n".join(str(value) for value in values if str(value).strip())


def _fallback_keyword_results(data: Dict[str, Any], top_k: int) -> List[Dict[str, Any]]:
    query = build_keyword_query_from_input(data)
    terms = [
        term
        for term in _query_terms(query)
        if term not in KEYWORD_STOP_TERMS
    ]
    docs = _read_knowledge_documents()

    scored = []
    for doc in docs:
        score = _keyword_score(doc["text"], terms)
        if score > 0:
            scored.append((score, doc))

    if not scored:
        scored = [(0.0, doc) for doc in docs]

    scored.sort(key=lambda item: item[0], reverse=True)

    results = []
    for rank, (score, item) in enumerate(scored[:top_k], start=1):
        source = item.get("source", "")
        results.append({
            "rank": rank,
            "score": round(float(score), 4),
            "source": source,
            "metadata": {
                "source": source,
                "source_file": source,
                "document_name": source,
            },
            "chunk_id": item.get("chunk_id", 0),
            "text": item.get("text", "")[:3000],
            "retrieval_mode": "keyword_fallback",
        })

    return results


def retrieve_pd_ecr_results(data: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
    query = build_query_from_input(data)

    if not query.strip():
        return []

    try:
        from app.rag.retrieval.embeddings import get_embeddings

        index, meta = load_faiss_index()
        if np is None:
            raise RuntimeError("numpy is not installed")
        embedder = get_embeddings()
    except Exception as exc:
        print(f"FAISS retrieval unavailable, using keyword fallback: {exc}")
        return _fallback_keyword_results(data, top_k=top_k)

    query_embedding = np.asarray([embedder.embed_query(query)], dtype="float32")

    scores, indices = index.search(query_embedding, max(top_k * 2, top_k))

    results = []

    for rank, idx in enumerate(indices[0]):
        if idx < 0:
            continue

        item = meta[idx]
        item_metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}

        score = float(scores[0][rank])
        results.append({
            "rank": rank + 1,
            "score": round(score, 4),
            "source": item.get("source", ""),
            "metadata": {
                **item_metadata,
                "source": item.get("source", ""),
                "source_file": item.get("source", ""),
                "document_name": item.get("source", ""),
                "document_type": item.get("document_type", ""),
                "case_id": item.get("case_id", ""),
                "chunk_type": item.get("chunk_type", item_metadata.get("chunk_type", "")),
            },
            "chunk_id": item.get("chunk_id", ""),
            "text": item.get("text", ""),
            "retrieval_mode": "faiss",
            "_hybrid_score": score,
        })

    keyword_results = _fallback_keyword_results(data, top_k=max(top_k * 2, top_k))
    max_keyword_score = max(
        [float(item.get("score", 0.0)) for item in keyword_results] or [1.0]
    )

    for item in keyword_results:
        keyword_score = float(item.get("score", 0.0))
        normalized_keyword_score = (
            keyword_score / max_keyword_score if max_keyword_score > 0 else 0.0
        )
        results.append({
            **item,
            "retrieval_mode": "hybrid_keyword",
            "_hybrid_score": 0.45 + (0.45 * normalized_keyword_score),
        })

    ranked = sorted(
        results,
        key=lambda item: float(item.get("_hybrid_score", item.get("score", 0.0))),
        reverse=True,
    )

    deduped = []
    seen = set()
    for item in ranked:
        key = (
            item.get("source", ""),
            item.get("chunk_id", ""),
            item.get("retrieval_mode", ""),
        )
        if key in seen:
            continue
        seen.add(key)

        hybrid_score = float(item.get("_hybrid_score", item.get("score", 0.0)))
        item = {key: value for key, value in item.items() if key != "_hybrid_score"}
        item["score"] = round(hybrid_score, 4)
        item["rank"] = len(deduped) + 1
        deduped.append(item)

        if len(deduped) >= top_k:
            break

    return deduped


def retrieve_pd_ecr_context(
    data: Dict[str, Any],
    top_k: int = 20,
    results: List[Dict[str, Any]] | None = None,
) -> str:
    """构建 RAG 上下文文本。

    如果调用方已经持有 results（例如刚调过 retrieve_pd_ecr_results），
    通过 results 参数传入可避免重复执行昂贵的 FAISS 检索。
    """
    if results is None:
        results = retrieve_pd_ecr_results(data, top_k=top_k)

    context_parts = []

    for item in results:
        context_parts.append(
            f"""【历史案例 {item["rank"]}】
来源文件：{item["source"]}
片段编号：{item["chunk_id"]}
匹配分数：{item["score"]}
内容：
{item["text"]}
"""
        )

    return "\n\n".join(context_parts)
