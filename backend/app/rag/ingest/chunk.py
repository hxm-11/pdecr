"""文本切分：用 LangChain RecursiveCharacterTextSplitter 替换旧的裸字符切分。

旧的 split_text 是按固定字符数硬切（会把句子/表格从中间截断）。
RecursiveCharacterTextSplitter 会优先在段落 -> 换行 -> 中英文句末 -> 空格
这些语义边界上切，中英混排的工程文档质量明显更好。

chunk_size / chunk_overlap 沿用旧值（800 / 120），保证新旧索引规模可对比。
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# 中英文混排的分隔优先级：段落 > 行 > 中文句末 > 英文句末 > 空格 > 字符
_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    ". ",
    "! ",
    "? ",
    "; ",
    "，",
    ", ",
    " ",
    "",
]


@lru_cache(maxsize=1)
def _get_splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_SEPARATORS,
        length_function=len,
        keep_separator=True,
    )


def chunk_text(text: str) -> List[str]:
    """把长文本切成语义块。空白块会被过滤掉。"""
    if not text or not text.strip():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = _get_splitter().split_text(text)
    return [c.strip() for c in chunks if c and c.strip()]
