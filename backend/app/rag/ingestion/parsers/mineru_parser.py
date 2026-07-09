"""MinerU 解析产物 -> ParsedDocument。

MinerU 会把 PDF 解析成 raw markdown + raw json（content_list / middle json）。
这里把两者读成统一的 ParsedDocument：markdown 作正文，json 里的
文本块 / 表格 / 图片说明尽量抽出来。

注意：MinerU 的 json 结构有多个版本（content_list.json 是扁平 block 列表；
middle.json 带 pdf_info -> preproc_blocks）。这里做防御式解析，两种都尽量兼容；
解析不出来也不报错，退化为只用 markdown。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..loaders import ParsedDocument, ParsedTable, compute_checksum, read_text_file


class MineruParser:
    parser_name = "mineru"

    def parse(
        self,
        raw_json_path: str | None,
        raw_markdown_path: str | None,
        source_file: str | None = None,
    ) -> ParsedDocument:
        if not raw_json_path and not raw_markdown_path:
            raise ValueError(
                "MineruParser 至少需要 raw_json_path 或 raw_markdown_path 之一"
            )

        raw_markdown: str | None = None
        if raw_markdown_path and Path(raw_markdown_path).exists():
            raw_markdown = read_text_file(raw_markdown_path)

        raw_json: dict[str, Any] | None = None
        json_blocks: list[Any] = []
        if raw_json_path and Path(raw_json_path).exists():
            raw_json, json_blocks = self._load_json(raw_json_path)

        tables, images, json_text = self._extract_from_blocks(json_blocks)

        # 正文优先用 markdown（可读性最好）；没有 markdown 时退化用 json 文本块
        text = raw_markdown if raw_markdown else json_text

        checksum = None
        checksum_target = raw_markdown_path or raw_json_path
        if checksum_target and Path(checksum_target).exists():
            checksum = compute_checksum(checksum_target)

        resolved_source = source_file or (
            Path(raw_markdown_path).name
            if raw_markdown_path
            else Path(raw_json_path).name  # type: ignore[arg-type]
        )

        return ParsedDocument(
            source_file=resolved_source,
            file_type="pdf",
            parser=self.parser_name,
            text=text or "",
            tables=tables,
            images=images,
            raw_json=raw_json,
            raw_markdown=raw_markdown,
            raw_json_path=str(raw_json_path) if raw_json_path else None,
            raw_markdown_path=str(raw_markdown_path) if raw_markdown_path else None,
            checksum=checksum,
        )

    # ── 内部 ──────────────────────────────────────────────
    @staticmethod
    def _load_json(raw_json_path: str) -> tuple[dict[str, Any] | None, list[Any]]:
        try:
            data = json.loads(read_text_file(raw_json_path))
        except (json.JSONDecodeError, OSError):
            return None, []

        # content_list.json：顶层就是 block 列表
        if isinstance(data, list):
            return {"content_list": data}, data

        blocks: list[Any] = []
        if isinstance(data, dict):
            # middle.json：pdf_info -> [{ preproc_blocks / para_blocks }]
            pdf_info = data.get("pdf_info")
            if isinstance(pdf_info, list):
                for page in pdf_info:
                    if not isinstance(page, dict):
                        continue
                    for key in ("preproc_blocks", "para_blocks", "blocks"):
                        val = page.get(key)
                        if isinstance(val, list):
                            blocks.extend(val)
            # 有些导出直接把 block 放 content_list 键
            if not blocks and isinstance(data.get("content_list"), list):
                blocks = data["content_list"]
        return (data if isinstance(data, dict) else None), blocks

    @staticmethod
    def _extract_from_blocks(
        blocks: list[Any],
    ) -> tuple[list[ParsedTable], list[dict[str, Any]], str]:
        tables: list[ParsedTable] = []
        images: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for idx, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type", "")).lower()

            if btype == "table" or "table_body" in block:
                caption = _join(block.get("table_caption"))
                body = block.get("table_body") or block.get("html") or ""
                tables.append(
                    ParsedTable(
                        name=caption or f"table_{idx}",
                        rows=[],  # MinerU 表格常是 html，不强行解析成二维
                        text="\n".join(p for p in [caption, str(body)] if p),
                    )
                )
            elif btype == "image" or "img_caption" in block or "img_path" in block:
                images.append(
                    {
                        "caption": _join(block.get("img_caption")),
                        "path": block.get("img_path") or block.get("image_path") or "",
                    }
                )
            else:
                txt = _block_text(block)
                if txt:
                    text_parts.append(txt)

        return tables, images, "\n".join(text_parts)


def _join(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(v) for v in value if v)
    return str(value)


def _block_text(block: dict[str, Any]) -> str:
    # content_list：{"type":"text","text":"..."}
    if isinstance(block.get("text"), str):
        return block["text"].strip()
    # middle.json：block -> lines -> spans -> content
    parts: list[str] = []
    for line in block.get("lines", []) or []:
        if not isinstance(line, dict):
            continue
        for span in line.get("spans", []) or []:
            if isinstance(span, dict) and span.get("content"):
                parts.append(str(span["content"]))
    return " ".join(parts).strip()
