"""PD-ECR 离线建库层：源文档 -> 切分 -> embedding -> FAISS 索引。

对外接口：
  - load_documents()  读取全部源，返回 chunk 列表
  - build()           构建并写出 FAISS 索引 + 元数据
  - rebuild_index()   线程安全重建（供后台任务/API 调用）
  - get_rebuild_status()

切分使用 LangChain RecursiveCharacterTextSplitter（见 ingest.chunk）。
"""

from .build_index import build, build_langchain_store, get_rebuild_status, rebuild_index
from .chunk import chunk_text
from .parse import load_documents

__all__ = [
    "build",
    "build_langchain_store",
    "rebuild_index",
    "get_rebuild_status",
    "load_documents",
    "chunk_text",
]
