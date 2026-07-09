"""Embedding 接入层：统一由 get_embeddings() 提供向量。

默认走 Azure OpenAI 兼容端点的 text-embedding-3-small

切换开关（.env）：
    EMBEDDING_BACKEND=azure   # 默认，调 API（推荐，和后端统一）
    EMBEDDING_BACKEND=local   # 回退到本地 sentence-transformers（离线/内网无出口时）

API 相关（缺省复用对话模型的 LLM_* 配置，通常无需单独配）：
    EMBEDDING_API_KEY    缺省用 LLM_API_KEY
    EMBEDDING_BASE_URL   缺省用 LLM_BASE_URL
    EMBEDDING_MODEL      缺省 text-embedding-3-small（1536 维）

注意：换 embedding 会改变向量维度（本地 384 -> 3-small 1536），
切换后必须重建索引：python -m app.rag.ingest.build_index
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_core.embeddings import Embeddings

MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


# ──────────────────────────────────────────────────────────────
# 本地 sentence-transformers（可选回退，EMBEDDING_BACKEND=local 时启用）
# ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_local_model():
    from sentence_transformers import SentenceTransformer

    if not MODEL_PATH.exists():
        raise RuntimeError(f"本地 embedding 模型不存在：{MODEL_PATH}")
    return SentenceTransformer(str(MODEL_PATH))


class LocalSentenceTransformerEmbeddings(Embeddings):
    """LangChain Embeddings 实现，归一化向量以配合余弦相似度（IndexFlatIP）。"""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = _load_local_model()
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> List[float]:
        model = _load_local_model()
        vec = model.encode([text], normalize_embeddings=True)[0]
        return vec.tolist()


# ──────────────────────────────────────────────────────────────
# Azure / OpenAI 兼容端点的 API embedding（默认）
# ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _build_azure_embeddings() -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = os.getenv("EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL")
    model = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    if not api_key:
        raise RuntimeError("缺少 EMBEDDING_API_KEY / LLM_API_KEY，请在 .env 中配置")

    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        # 关闭基于 tiktoken 的本地分词/截断：避免内网无出口时 tiktoken 下载编码表失败；
        # chunk 已由 RecursiveCharacterTextSplitter 切小，交给服务端处理长度即可。
        "check_embedding_ctx_length": False,
    }
    if base_url:
        kwargs["base_url"] = base_url
    # text-embedding-3-* 官方返回单位向量，内积 ≈ 余弦，无需再手动归一化。
    return OpenAIEmbeddings(**kwargs)


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    backend = os.getenv("EMBEDDING_BACKEND", "azure").strip().lower()
    if backend == "local":
        return LocalSentenceTransformerEmbeddings()
    return _build_azure_embeddings()
