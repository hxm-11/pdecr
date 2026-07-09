"""统一文档载入层：把任意来源文件读成 :class:`ParsedDocument`。

ParsedDocument 是 parser 层的统一输出格式，抽取器只认它，不关心源是
PDF / Excel / Word。新增来源只需实现一个 parser 并在这里登记映射。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedTable:
    """一个表格：二维单元格 + 渲染好的文本（供抽取/切分直接读）。"""

    name: str = ""
    rows: list[list[str]] = field(default_factory=list)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "rows": self.rows, "text": self.text}


@dataclass
class ParsedDocument:
    """所有 parser 的统一输出。"""

    source_file: str
    file_type: str = ""  # pdf / xlsx / xls / docx / db_export
    parser: str = ""  # mineru / excel / word / db_export
    text: str = ""
    tables: list[ParsedTable] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)
    raw_json: dict[str, Any] | None = None
    raw_markdown: str | None = None
    raw_json_path: str | None = None
    raw_markdown_path: str | None = None
    checksum: str | None = None

    def full_text(self) -> str:
        """正文 + 所有表格文本，供 rule-based / LLM 抽取器读取。"""
        parts = [self.text or ""]
        for tbl in self.tables:
            if tbl.text:
                parts.append(tbl.text)
        return "\n\n".join(p for p in parts if p.strip())


def compute_checksum(path: str | Path) -> str:
    """文件内容 SHA-256（用于 registry 判重 / 变更 reindex）。"""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def read_text_file(path: str | Path) -> str:
    """兼容 utf-8 / gbk 的文本读取。"""
    p = Path(path)
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="gbk", errors="ignore")


# ── 来源分发 ──────────────────────────────────────────────────
# 后续新增 DatabaseExportParser 只需在这里加分支。
_EXCEL_SUFFIXES = {".xlsx", ".xls", ".xlsm"}


def detect_source_type(path: str | Path) -> str:
    """按扩展名粗判来源类型。"""
    suffix = Path(path).suffix.lower()
    if suffix in _EXCEL_SUFFIXES:
        return "excel"
    if suffix == ".pdf":
        return "mineru"  # PDF 走 MinerU 解析产物
    if suffix in {".docx", ".doc"}:
        return "word"
    return "unknown"


def load_parsed_document(
    path: str | Path, source_type: str | None = None
) -> ParsedDocument:
    """按类型分发到对应 parser，返回 ParsedDocument。

    对 mineru（PDF）来说通常应直接调用 MineruParser（因为它需要 raw json +
    raw markdown 两个路径）；这里的分发主要服务 Excel/Word 这类单文件来源。
    """
    source_type = source_type or detect_source_type(path)

    if source_type == "excel":
        from .parsers.excel_parser import ExcelParser

        return ExcelParser().parse(str(path))

    if source_type == "word":
        from .parsers.word_parser import WordParser

        return WordParser().parse(str(path))

    raise ValueError(
        f"未知或需专用入口的来源类型: {source_type} ({path})。"
        "PDF/MinerU 请用 MineruParser.parse(raw_json_path, raw_markdown_path)。"
    )
