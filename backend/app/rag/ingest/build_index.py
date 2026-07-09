"""离线建库：源文档 -> 切分 -> embedding -> FAISS 索引。

产出与旧版一致，写到 app/rag/vector_store/：
  - pd_ecr.faiss           FAISS 索引（IndexFlatIP，余弦相似度）
  - pd_ecr_meta.pkl        与向量一一对应的 chunk 元数据（list[dict]）
  - pd_ecr_rebuild_status.json  最近一次重建状态

因此现有检索层（app.rag.retriever / app.rag.retrieval）无需改动即可读新索引。

用法（backend/ 目录）::

    python -m app.rag.ingest.build_index          # 全量重建
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Dict, List

from .parse import load_documents

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent  # app/rag
VECTOR_DIR = BASE_DIR / "vector_store"
MODEL_PATH = BASE_DIR / "models" / "paraphrase-multilingual-MiniLM-L12-v2"

INDEX_PATH = VECTOR_DIR / "pd_ecr.faiss"
META_PATH = VECTOR_DIR / "pd_ecr_meta.pkl"
_STATUS_PATH = VECTOR_DIR / "pd_ecr_rebuild_status.json"

# LangChain 原生 FAISS 向量库目录（供 EnsembleRetriever 使用，与上面的 raw 索引并存）
LC_STORE_DIR = VECTOR_DIR / "langchain_faiss"


def build(docs: List[Dict] | None = None) -> int:
    """构建索引，返回写入的 chunk 数。"""
    import faiss
    import numpy as np

    from app.rag.retrieval.embeddings import get_embeddings

    if docs is None:
        docs = load_documents()

    if not docs:
        print("没有找到知识库文件，请检查 app/rag/knowledge、jie_jim_knowledge_pdf、PDECR_JIE_JIM/docling_output")
        return 0

    print(f"共读取 {len(docs)} 个文本片段（RecursiveCharacterTextSplitter 切分）")

    # 与 build_langchain_store / 检索层用同一个 embedding 源（默认 Azure API）
    embedder = get_embeddings()
    texts = [doc["text"] for doc in docs]
    embeddings = np.asarray(embedder.embed_documents(texts), dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(docs, f)

    print("RAG 索引构建完成")
    print("Index:", INDEX_PATH)
    print("Meta: ", META_PATH)
    return len(docs)


def build_langchain_store(docs: List[Dict] | None = None) -> int:
    """构建 LangChain 原生 FAISS 向量库（供 EnsembleRetriever 的稠密检索用）。

    与 raw 索引用同一批 chunk、同一个本地 embedding 模型，只是存成
    LangChain 的 save_local 格式（LC_STORE_DIR/index.faiss + index.pkl），
    这样可以直接 .as_retriever() 并接进 EnsembleRetriever / 重排。
    """
    from langchain_community.vectorstores import FAISS
    from langchain_community.vectorstores.utils import DistanceStrategy
    from langchain_core.documents import Document

    from app.rag.retrieval.embeddings import get_embeddings

    if docs is None:
        docs = load_documents()
    if not docs:
        print("没有可索引的文档，跳过 LangChain 向量库构建")
        return 0

    print(f"构建 LangChain FAISS 向量库：{len(docs)} 个片段")
    lc_docs = [
        Document(
            page_content=d["text"],
            metadata={
                "source": d.get("source", ""),
                "chunk_id": d.get("chunk_id", ""),
                "document_type": d.get("document_type", ""),
                "case_id": d.get("case_id", ""),
                "chunk_type": d.get("chunk_type", ""),
                **(d.get("metadata") if isinstance(d.get("metadata"), dict) else {}),
            },
        )
        for d in docs
    ]

    # 用内积（MAX_INNER_PRODUCT）对齐旧的 IndexFlatIP；向量已归一化 => 等价余弦相似度
    store = FAISS.from_documents(
        lc_docs,
        get_embeddings(),
        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
    )
    LC_STORE_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(LC_STORE_DIR))
    print("LangChain 向量库已保存：", LC_STORE_DIR)
    return len(lc_docs)


# ── 重建状态 + 并发锁（供 API/UI 调用，沿用旧接口）──
_index_lock = None


def _get_index_lock():
    global _index_lock
    if _index_lock is None:
        import threading

        _index_lock = threading.Lock()
    return _index_lock


def _write_rebuild_status(success: bool, doc_count: int, error: str = "") -> None:
    import json as _json
    from datetime import datetime, timezone

    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    _STATUS_PATH.write_text(
        _json.dumps(
            {
                "last_rebuild_at": datetime.now(timezone.utc).isoformat(),
                "success": success,
                "total_documents": doc_count,
                "error": error,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def get_rebuild_status() -> dict | None:
    import json as _json

    if not _STATUS_PATH.exists():
        return None
    try:
        return _json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def rebuild_index() -> bool:
    """线程安全的重建（后台任务调用）。成功返回 True。"""
    lock = _get_index_lock()
    if not lock.acquire(blocking=False):
        print("FAISS 索引重建已在进行中，跳过。")
        return False
    try:
        docs = load_documents()
        count = build(docs=docs)
        build_langchain_store(docs=docs)
        _write_rebuild_status(success=True, doc_count=count)
        return True
    except Exception:
        import traceback

        err = traceback.format_exc()
        traceback.print_exc()
        _write_rebuild_status(success=False, doc_count=0, error=str(err))
        return False
    finally:
        lock.release()


if __name__ == "__main__":
    # 独立运行建库脚本时手动加载 .env（LLM_API_KEY / LLM_BASE_URL 等）；
    # 跑在 FastAPI 内时由应用配置加载，无需这行。
    from dotenv import load_dotenv

    load_dotenv()

    _docs = load_documents()
    build(docs=_docs)
    build_langchain_store(docs=_docs)
