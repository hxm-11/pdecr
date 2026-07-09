"""PD-ECR 检索层：查询 -> 相似历史案例上下文。

对外只暴露一个干净接口 :func:`retrieve_cases`，内部当前复用已建好的
FAISS 索引（app/rag/vector_store/pd_ecr.faiss），后续可平滑替换成
LangChain 原生 FAISS vectorstore 而不影响 graph 层。
"""

from .retriever import RetrievedChunk, retrieve_cases

__all__ = ["RetrievedChunk", "retrieve_cases"]
