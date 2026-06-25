from __future__ import annotations

import re
import posixpath
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile
from xml.etree import ElementTree as ET

REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
VML_NS = "{urn:schemas-microsoft-com:vml}"
EXCEL_NS = "{urn:schemas-microsoft-com:office:excel}"


def extract_xlsx_controls(file_path: Path) -> list[dict[str, Any]]:
    """Extract checkbox controls from an .xlsx/.xlsm package without Excel.

    The parser reads worksheet relationships and VML drawings directly from the
    OOXML zip. This is the server-safe path; Windows COM can still be used as a
    local enhancement elsewhere, but this function has no platform dependency.
    """

    if file_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return []

    with ZipFile(file_path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheets = _read_workbook_sheets(archive)
        controls: list[dict[str, Any]] = []

        for sheet in sheets:
            sheet_path = sheet["path"]
            cells = _read_sheet_cells(archive, sheet_path, shared_strings)
            vml_paths = _sheet_vml_paths(archive, sheet_path)

            for vml_path in vml_paths:
                controls.extend(
                    _read_vml_checkboxes(
                        archive=archive,
                        vml_path=vml_path,
                        sheet_name=sheet["name"],
                        cells=cells,
                    )
                )

    return controls


def _read_xml(archive: ZipFile, name: str) -> ET.Element | None:
    try:
        data = archive.read(name)
    except KeyError:
        return None

    try:
        return ET.fromstring(data)
    except ET.ParseError:
        return None


def _read_workbook_sheets(archive: ZipFile) -> list[dict[str, str]]:
    workbook = _read_xml(archive, "xl/workbook.xml")
    rels = _read_xml(archive, "xl/_rels/workbook.xml.rels")
    if workbook is None or rels is None:
        return []

    targets_by_id = {
        rel.attrib.get("Id"): _resolve_package_path("xl/workbook.xml", rel.attrib.get("Target", ""))
        for rel in rels.findall(f"{REL_NS}Relationship")
    }

    sheets: list[dict[str, str]] = []
    for sheet in workbook.findall(f".//{MAIN_NS}sheet"):
        rel_id = sheet.attrib.get(f"{OFFICE_REL_NS}id")
        target = targets_by_id.get(rel_id)
        if target:
            sheets.append({"name": sheet.attrib.get("name", ""), "path": target})
    return sheets


def _read_shared_strings(archive: ZipFile) -> list[str]:
    root = _read_xml(archive, "xl/sharedStrings.xml")
    if root is None:
        return []

    values: list[str] = []
    for item in root.findall(f"{MAIN_NS}si"):
        text = "".join(t.text or "" for t in item.findall(f".//{MAIN_NS}t"))
        values.append(_clean_text(text))
    return values


def _read_sheet_cells(
    archive: ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> dict[str, str]:
    root = _read_xml(archive, sheet_path)
    if root is None:
        return {}

    cells: dict[str, str] = {}
    for cell in root.findall(f".//{MAIN_NS}c"):
        ref = cell.attrib.get("r")
        if not ref:
            continue
        value = _cell_value(cell, shared_strings)
        if value:
            cells[ref.upper()] = value
    return cells


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        return _clean_text("".join(t.text or "" for t in cell.findall(f".//{MAIN_NS}t")))

    raw = cell.find(f"{MAIN_NS}v")
    if raw is None or raw.text is None:
        return ""

    if cell_type == "s":
        try:
            return shared_strings[int(raw.text)]
        except (ValueError, IndexError):
            return ""

    return _clean_text(raw.text)


def _sheet_vml_paths(archive: ZipFile, sheet_path: str) -> list[str]:
    rels_path = _relationships_path(sheet_path)
    rels = _read_xml(archive, rels_path)
    if rels is None:
        return []

    vml_paths: list[str] = []
    for rel in rels.findall(f"{REL_NS}Relationship"):
        rel_type = rel.attrib.get("Type", "")
        if not rel_type.endswith("/vmlDrawing"):
            continue
        target = rel.attrib.get("Target", "")
        if target:
            vml_paths.append(_resolve_package_path(sheet_path, target))
    return vml_paths


def _read_vml_checkboxes(
    *,
    archive: ZipFile,
    vml_path: str,
    sheet_name: str,
    cells: dict[str, str],
) -> list[dict[str, Any]]:
    root = _read_xml(archive, vml_path)
    if root is None:
        return []

    controls: list[dict[str, Any]] = []
    for shape in root.findall(f".//{VML_NS}shape"):
        client_data = shape.find(f"{EXCEL_NS}ClientData")
        if client_data is None:
            continue
        if client_data.attrib.get("ObjectType", "").lower() != "checkbox":
            continue

        anchor = _first_child_text(client_data, "Anchor")
        col, row = _anchor_to_col_row(anchor)
        if col is None or row is None:
            continue

        cell_ref = f"{_column_name(col + 1)}{row + 1}"
        caption = _shape_caption(shape) or cells.get(cell_ref, "") or shape.attrib.get("id", "")
        checked = _first_child_text(client_data, "Checked").strip() in {"1", "true", "True"}

        controls.append(
            {
                "type": "checkbox",
                "sheet": sheet_name,
                "cell": cell_ref,
                "caption": caption,
                "checked": checked,
                "value": _caption_value(caption),
                "nearby_label": _nearby_label(cells, row + 1, col + 1),
                "source": "xlsx_xml",
            }
        )

    return controls


def _relationships_path(part_path: str) -> str:
    part = PurePosixPath(part_path)
    return str(part.parent / "_rels" / f"{part.name}.rels")


def _resolve_package_path(base_part: str, target: str) -> str:
    target_path = PurePosixPath(target)
    if target.startswith("/"):
        return str(target_path).lstrip("/")
    base = PurePosixPath(base_part).parent
    return posixpath.normpath(str(base / target_path)).lstrip("/")


def _anchor_to_col_row(anchor: str) -> tuple[int | None, int | None]:
    parts = [p.strip() for p in anchor.split(",")]
    if len(parts) < 3:
        return None, None
    try:
        return int(parts[0]), int(parts[2])
    except ValueError:
        return None, None


def _shape_caption(shape: ET.Element) -> str:
    textbox = shape.find(f"{VML_NS}textbox")
    if textbox is None:
        return ""
    return _clean_text(" ".join(textbox.itertext()))


def _first_child_text(parent: ET.Element, local_name: str) -> str:
    for child in parent:
        if child.tag.endswith(f"}}{local_name}") or child.tag == local_name:
            return child.text or ""
    return ""


def _caption_value(caption: str) -> str:
    text = caption.strip().lower()
    if "yes" in text or "是" in text:
        return "yes"
    if "no" in text or "否" in text:
        return "no"
    if text in {"y", "n"}:
        return text
    return caption.strip()


def _nearby_label(cells: dict[str, str], row: int, col: int) -> str:
    ignored = {"yes", "yes/是", "no", "no/否", "y", "n", "是", "否"}

    for current_col in range(col - 1, 0, -1):
        value = cells.get(f"{_column_name(current_col)}{row}", "").strip()
        if value and value.lower() not in ignored:
            return value

    for prev_row in range(row - 1, max(0, row - 4), -1):
        row_values = [
            value.strip()
            for ref, value in cells.items()
            if _cell_row(ref) == prev_row and value.strip()
        ]
        if row_values:
            return " | ".join(row_values[:4])

    return ""


def _cell_row(ref: str) -> int | None:
    match = re.search(r"(\d+)$", ref)
    return int(match.group(1)) if match else None


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())
