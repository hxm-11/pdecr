from __future__ import annotations

import zipfile
from pathlib import Path

from app.rag.ingestion import pipeline
from app.rag.ingestion.parsers.word_parser import WordParser


def _write_docx(path: Path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>变更原因: 客户要求释放A样件</w:t></w:r></w:p>
    <w:p><w:r><w:t>变更方案: 增加倒角并更新图纸</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>字段</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>内容</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>验证计划</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Trial Run</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


def test_word_parser_reads_docx_paragraphs_and_tables(tmp_path: Path) -> None:
    docx_path = tmp_path / "PDECR_WORD_001.docx"
    _write_docx(docx_path)

    parsed = WordParser().parse(str(docx_path))

    assert parsed.file_type == "docx"
    assert parsed.parser == "word"
    assert "客户要求释放A样件" in parsed.text
    assert parsed.tables
    assert "Trial Run" in parsed.tables[0].text
    assert parsed.checksum


def test_directory_ingest_auto_discovers_docx(tmp_path: Path) -> None:
    docx_path = tmp_path / "PDECR_WORD_001.docx"
    _write_docx(docx_path)

    cases = pipeline.ingest_case_directory(str(tmp_path), source_type="auto")

    assert len(cases) == 1
    assert cases[0].source.file_type == "docx"
    assert cases[0].modules.change_reason
