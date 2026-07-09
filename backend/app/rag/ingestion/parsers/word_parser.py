"""Word (.docx) -> ParsedDocument.

The parser uses only the Python standard library so historical PD-ECR Word
files can be ingested without adding another runtime dependency. Legacy .doc
files are not zip/xml documents; convert them to .docx or PDF first.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from ..loaders import ParsedDocument, ParsedTable, compute_checksum

_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class WordParser:
    parser_name = "word"

    def parse(self, word_path: str) -> ParsedDocument:
        path = Path(word_path)
        if not path.exists():
            raise FileNotFoundError(word_path)

        suffix = path.suffix.lower()
        if suffix == ".doc":
            raise RuntimeError("暂不支持旧版 .doc，请先另存为 .docx 或转成 PDF/MinerU 产物")
        if suffix != ".docx":
            raise ValueError(f"不支持的 Word 文件类型: {suffix}")

        text, tables = self._parse_docx(path)
        return ParsedDocument(
            source_file=path.name,
            file_type="docx",
            parser=self.parser_name,
            text=text,
            tables=tables,
            checksum=compute_checksum(path),
        )

    @staticmethod
    def _parse_docx(path: Path) -> tuple[str, list[ParsedTable]]:
        try:
            with zipfile.ZipFile(path) as zf:
                xml = zf.read("word/document.xml")
        except KeyError as exc:
            raise RuntimeError(f"不是有效的 .docx 文件，缺少 word/document.xml: {path}") from exc
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"不是有效的 .docx zip 文件: {path}") from exc

        root = ET.fromstring(xml)
        body = root.find("w:body", _NS)
        if body is None:
            return "", []

        paragraphs: list[str] = []
        tables: list[ParsedTable] = []
        table_index = 1

        for child in body:
            tag = _local_name(child.tag)
            if tag == "p":
                text = _paragraph_text(child)
                if text:
                    paragraphs.append(text)
            elif tag == "tbl":
                table = _table_from_xml(f"Word Table {table_index}", child)
                table_index += 1
                if table.rows:
                    tables.append(table)

        return "\n".join(paragraphs), tables


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _paragraph_text(node: ET.Element) -> str:
    parts: list[str] = []
    for text_node in node.findall(".//w:t", _NS):
        if text_node.text:
            parts.append(text_node.text)
    return "".join(parts).strip()


def _table_from_xml(name: str, table_node: ET.Element) -> ParsedTable:
    rows: list[list[str]] = []
    for row_node in table_node.findall("w:tr", _NS):
        row: list[str] = []
        for cell_node in row_node.findall("w:tc", _NS):
            cell_parts = [
                _paragraph_text(p)
                for p in cell_node.findall("w:p", _NS)
                if _paragraph_text(p)
            ]
            row.append("\n".join(cell_parts).strip())
        if any(row):
            rows.append(row)

    lines = [f"# {name}"]
    for row in rows:
        lines.append("\t".join(row))
    return ParsedTable(name=name, rows=rows, text="\n".join(lines))
