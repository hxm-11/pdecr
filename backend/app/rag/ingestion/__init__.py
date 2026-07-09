"""标准化 PD-ECR 案例 ingestion pipeline。

区别于 app/rag/ingest（那是把既有语料切分建 FAISS 向量库的离线建库层），
本包负责把任意来源（MinerU/PDF、Excel、Word、系统表单导出）先统一成标准
PdecrCase JSON，再由它渲染 markdown、按业务模块切 chunk、写本地/向量索引。

主入口：
  - ingest_mineru_case / ingest_excel_case / ingest_case_directory  (pipeline)
  - index_case / search_similar                                     (indexer)
  - Registry                                                        (registry)
"""

from .chunker import Chunk, build_chunks
from .indexer import index_case, save_chunks, search_similar
from .loaders import ParsedDocument, ParsedTable
from .markdown_renderer import render_markdown
from .normalizer import normalize_case
from .pipeline import (
    ingest_case_directory,
    ingest_excel_case,
    ingest_mineru_case,
)
from .registry import Registry

__all__ = [
    "Chunk",
    "ParsedDocument",
    "ParsedTable",
    "Registry",
    "build_chunks",
    "index_case",
    "ingest_case_directory",
    "ingest_excel_case",
    "ingest_mineru_case",
    "normalize_case",
    "render_markdown",
    "save_chunks",
    "search_similar",
]
